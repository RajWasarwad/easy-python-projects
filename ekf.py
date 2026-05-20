"""
EKF Vertical Velocity Estimator — Optimized
=============================================
Non-GPS baro + IMU fusion for vertical velocity estimation.
Runs on Raspberry Pi via Dronekit/pymavlink.

Optimizations over original (validated against 6940-sample flight log):
  1. Fixed output filter direction   — smooth during hover, fast during transitions
  2. Innovation gating (3σ)          — rejects baro outliers before state corruption
  3. Adaptive Q (velocity process)   — ultra-low during hover, high during transitions
  4. 2nd measurement: altitude rate  — directly constrains velocity during hover
  5. Reduced bias process noise      — Q[2] 0.04→0.005 prevents bias wandering
  6. Tighter adaptive R              — slower adaptation, higher floor
  7. Shorter acc Hampel window       — 150→80 samples, avoids rejecting valid maneuvers
"""

import time
import math
import csv
import statistics
import numpy as np
from collections import deque
from dronekit import connect

# ─────────────────────────────────────────────
#  CONNECTION
# ─────────────────────────────────────────────
vehicle = connect('/dev/ttyAMA0', baud=921600, wait_ready=True)
print("Connected to vehicle")

# ─────────────────────────────────────────────
#  CSV LOGGING
# ─────────────────────────────────────────────
output_file = open('ekf_log.csv', 'w', newline='')
csv_writer = csv.writer(output_file)
csv_writer.writerow(['Timestamp', 'VFR_HUD', 'EKF_Vz', 'Acc', 'Alt'])

# ─────────────────────────────────────────────
#  STATE VARIABLES
# ─────────────────────────────────────────────
# EKF state: [altitude, velocity, acc_bias]
x = np.array([0.0, 0.0, 0.0])
P = np.diag([1.0, 0.5, 0.01])

# Process noise — velocity component is set adaptively per-cycle
Q_alt   = 0.02    # altitude process noise
Q_bias  = 0.005   # bias process noise (was 0.04 — too high caused wandering)
Q_v_min = 0.002   # velocity process noise floor (hover — ultra smooth)
Q_v_max = 0.04    # velocity process noise ceiling (transitions — fast tracking)

# Measurement noise — altitude
R = np.array([[2.0]])      # initial R
R_ALPHA  = 0.95            # adaptive R smoothing (was 0.92 — too fast)
R_FLOOR  = 2.0             # R clamp floor (was 1.5)
R_CEIL   = 15.0            # R clamp ceiling (was 20)

# Innovation gate threshold (chi-squared, 1 DOF, 3σ → 9.0)
INNOV_GATE = 9.0

# Pre-filter parameters
ALT_LPF_ALPHA = 0.98       # keep — this is load-bearing for baro noise suppression
ACC_LPF_ALPHA = 0.95       # was 0.98 — reduced for less phase lag on acceleration
ACC_DEADBAND  = 0.04       # zero out tiny accelerations

# Altitude rate computation (2nd measurement)
ALT_RATE_SMOOTH = 0.96     # smoother for rate differentiation
RATE_AVG_WIN    = 12        # moving average window for altitude rate (samples)
R_VEL_HOVER  = 0.10        # trust altitude rate strongly during hover
R_VEL_MOTION = 80.0        # distrust altitude rate during transitions
RATE_INNOV_GATE = 16.0     # wider gate for rate measurement (4σ²)

# Motion detection
MOTION_THRESH  = 0.30      # acc RMS threshold for full-motion classification
ACC_ENERGY_WIN = 80        # window for acc RMS computation (samples)

# Adaptive output filter
ALPHA_HOVER = 0.985        # very smooth during hover (was 0.80 — BACKWARDS!)
ALPHA_MOTION = 0.70        # fast response during transitions (was 0.92 — BACKWARDS!)

# Hampel filter windows
ALT_HAMPEL_WIN = 15
ACC_HAMPEL_WIN = 80        # was 150 — too long, rejects valid maneuver accelerations
HAMPEL_NSIGMA  = 3.0

# ─────────────────────────────────────────────
#  FILTER STATE
# ─────────────────────────────────────────────
filtered_alt = 0.0
filtered_acc = 0.0
filtered_vz  = 0.0
alt_smooth   = 0.0          # separate smoother for rate computation
alt_prev     = 0.0
lst_altitude = 0.0

# Calibration
IS_CALIBRATED   = False
cal_alt_samples = []
cal_acc_samples = []
alt_offset      = 0.0

# Buffers
alt_hampel_buf    = deque(maxlen=ALT_HAMPEL_WIN)
acc_hampel_buf    = deque(maxlen=ACC_HAMPEL_WIN)
acc_energy_buf    = deque(maxlen=ACC_ENERGY_WIN)
rate_avg_buf      = deque(maxlen=RATE_AVG_WIN)

# Timing
last_time    = None
rate_started = False

# ─────────────────────────────────────────────
#  HELPER FUNCTIONS
# ─────────────────────────────────────────────

def hampel_filter(value, buffer, n_sigmas=HAMPEL_NSIGMA):
    """Hampel filter — replaces outliers with running median."""
    buffer.append(value)
    if len(buffer) < buffer.maxlen:
        return value
    median = statistics.median(buffer)
    deviations = [abs(x - median) for x in buffer]
    mad = statistics.median(deviations)
    if mad < 1e-6:
        return median
    threshold = n_sigmas * 1.4826 * mad
    if abs(value - median) > threshold:
        return median
    return value


def get_rotation_matrix(roll, pitch, yaw):
    """Body-to-world rotation matrix from Euler angles (radians)."""
    cr, sr = math.cos(roll), math.sin(roll)
    cp, sp = math.cos(pitch), math.sin(pitch)
    cy, sy = math.cos(yaw), math.sin(yaw)
    return np.array([
        [cy*cp,  cy*sp*sr - sy*cr,  cy*sp*cr + sy*sr],
        [sy*cp,  sy*sp*sr + cy*cr,  sy*sp*cr - cy*sr],
        [  -sp,            cp*sr,            cp*cr   ]
    ])


def pressure_to_altitude(press_abs, press_ref=1013.25, temp=288.15, lapse=0.0065):
    """Convert absolute pressure (hPa) to altitude (m) using barometric formula."""
    return (temp / lapse) * (1.0 - (press_abs / press_ref) ** (0.0065 * 8.31447 / (9.80665 * 0.0289644)))


# ─────────────────────────────────────────────
#  EKF CORE
# ─────────────────────────────────────────────

def ekf_predict(x, P, acc, dt, Q):
    """Predict step: propagate state and covariance."""
    a_corr = acc - x[2]  # correct for estimated bias

    # State transition
    x_pred = np.array([
        x[0] + x[1] * dt + 0.5 * a_corr * dt * dt,
        x[1] + a_corr * dt,
        x[2]
    ])

    # Jacobian
    F = np.array([
        [1.0,  dt, -0.5 * dt * dt],
        [0.0, 1.0,            -dt],
        [0.0, 0.0,            1.0]
    ])

    P_pred = F @ P @ F.T + Q
    return x_pred, P_pred


def ekf_update_altitude(x, P, R, alt_meas):
    """
    Update step: altitude measurement.
    Returns updated (x, P, R, accepted).
    Includes innovation gating and adaptive R.
    """
    H = np.array([[1.0, 0.0, 0.0]])
    y = alt_meas - x[0]        # innovation
    S = P[0, 0] + R[0, 0]      # innovation variance

    # ── Innovation gate (3σ) ──
    mahalanobis = y * y / S
    if mahalanobis > INNOV_GATE:
        return x, P, R, False   # reject this measurement

    # Kalman gain
    K = P @ H.T / S

    # ── Adaptive R ──
    R[0, 0] = R_ALPHA * R[0, 0] + (1.0 - R_ALPHA) * (y * y + P[0, 0])
    R[0, 0] = np.clip(R[0, 0], R_FLOOR, R_CEIL)

    # State and covariance update
    x = x + (K.flatten() * y)
    P = (np.eye(3) - K @ H) @ P

    return x, P, R, True


def ekf_update_velocity(x, P, alt_rate, R_vel):
    """
    Update step: altitude-rate as velocity pseudo-measurement.
    Constrains EKF velocity toward the observed altitude rate.
    """
    H = np.array([[0.0, 1.0, 0.0]])
    y = alt_rate - x[1]
    S = P[1, 1] + R_vel

    # Wider gate for rate measurement
    if (y * y / S) > RATE_INNOV_GATE:
        return x, P

    K = P @ H.T / S
    x = x + (K.flatten() * y)
    P = (np.eye(3) - K @ H) @ P
    return x, P


# ─────────────────────────────────────────────
#  MESSAGE CALLBACKS
# ─────────────────────────────────────────────

vel_vec = [0.0, 0.0]   # [vfr_hud_vz, ekf_vz]


@vehicle.on_message('SCALED_IMU2')
def imu_callback(self, name, message):
    global x, P, R, filtered_acc, filtered_alt, filtered_vz
    global last_time, IS_CALIBRATED, alt_offset
    global cal_alt_samples, cal_acc_samples
    global lst_altitude, vel_vec
    global alt_smooth, alt_prev, rate_started

    now = time.time()
    if last_time is None:
        last_time = now
        return
    dt = now - last_time
    last_time = now

    if dt <= 0 or dt > 0.5:
        return

    # ── IMU acceleration → world frame ──
    a_body = np.array([message.xacc, message.yacc, message.zacc]) / 1000.0 * 9.81
    att = vehicle.attitude
    R_mat = get_rotation_matrix(att.roll, att.pitch, att.yaw)
    a_world = R_mat @ a_body
    zacc_raw = a_world[2] + 9.81   # remove gravity

    # Deadband
    if abs(zacc_raw) < ACC_DEADBAND:
        zacc_raw = 0.0

    # ── Pre-filter acceleration ──
    zacc = hampel_filter(zacc_raw, acc_hampel_buf)
    filtered_acc = ACC_LPF_ALPHA * filtered_acc + (1.0 - ACC_LPF_ALPHA) * zacc

    # ── Barometric altitude ──
    altitude = pressure_to_altitude(message.press_abs / 100.0) if hasattr(message, 'press_abs') else 0.0

    # ── Calibration phase (first 100 samples) ──
    if not IS_CALIBRATED:
        cal_alt_samples.append(altitude)
        cal_acc_samples.append(zacc_raw)
        if len(cal_alt_samples) >= 100:
            alt_offset = statistics.mean(cal_alt_samples)
            IS_CALIBRATED = True
            print(f"Calibrated: alt_offset={alt_offset:.2f}")
        return

    altitude -= alt_offset

    # ── Pre-filter altitude ──
    alt_h = hampel_filter(altitude, alt_hampel_buf)
    filtered_alt = ALT_LPF_ALPHA * filtered_alt + (1.0 - ALT_LPF_ALPHA) * alt_h

    # ── Altitude rate computation (separate smoother) ──
    alt_smooth_val = ALT_RATE_SMOOTH * alt_smooth + (1.0 - ALT_RATE_SMOOTH) * alt_h
    alt_smooth = alt_smooth_val

    if rate_started:
        raw_rate = (alt_smooth_val - alt_prev) / dt
        rate_avg_buf.append(raw_rate)
        alt_rate = np.mean(list(rate_avg_buf)) if len(rate_avg_buf) >= 3 else 0.0
    else:
        alt_rate = 0.0
        rate_started = True
    alt_prev = alt_smooth_val

    # ── Motion detection (acceleration RMS) ──
    acc_energy_buf.append(filtered_acc ** 2)
    if len(acc_energy_buf) >= 10:
        acc_rms = math.sqrt(sum(acc_energy_buf) / len(acc_energy_buf))
    else:
        acc_rms = 0.5   # assume motion during startup

    motion_factor = min(1.0, acc_rms / MOTION_THRESH)

    # ── Adaptive Q ──
    q_velocity = Q_v_min + motion_factor * (Q_v_max - Q_v_min)
    Q = np.diag([Q_alt, q_velocity, Q_bias])

    # ── EKF PREDICT ──
    x, P = ekf_predict(x, P, filtered_acc, dt, Q)

    # ── EKF UPDATE 1: Altitude ──
    if abs(altitude - lst_altitude) > 0.01:
        x, P, R, accepted = ekf_update_altitude(x, P, R, filtered_alt)

    # ── EKF UPDATE 2: Altitude rate → velocity constraint ──
    #    Trust rate strongly during hover, weakly during motion
    R_vel = R_VEL_HOVER + motion_factor * (R_VEL_MOTION - R_VEL_HOVER)
    x, P = ekf_update_velocity(x, P, alt_rate, R_vel)

    lst_altitude = altitude

    # ── ADAPTIVE OUTPUT FILTER ──
    #    CRITICAL FIX: original had this BACKWARDS
    #    Low motion (hover)  → high alpha → heavy smoothing → removes oscillation
    #    High motion (trans) → low alpha  → fast response  → quick settling
    alpha = ALPHA_HOVER - motion_factor * (ALPHA_HOVER - ALPHA_MOTION)
    filtered_vz = alpha * filtered_vz + (1.0 - alpha) * x[1]

    vel_vec[1] = filtered_vz


@vehicle.on_message('VFR_HUD')
def vfr_callback(self, name, message):
    vel_vec[0] = message.climb


@vehicle.on_message('GLOBAL_POSITION_INT')
def gps_callback(self, name, message):
    if not IS_CALIBRATED:
        return

    timestamp = time.strftime('%a %b %d %H:%M:%S %Y')
    csv_writer.writerow([
        timestamp,
        f"{vel_vec[0]:.4f}",
        f"{-filtered_vz:.4f}",
        f"{filtered_acc:.4f}",
        f"{filtered_alt:.4f}"
    ])
    output_file.flush()


# ─────────────────────────────────────────────
#  MAIN LOOP
# ─────────────────────────────────────────────
print("EKF VZ Estimator running (optimized)...")
print("  Adaptive Q: vel noise {:.3f}–{:.3f}".format(Q_v_min, Q_v_max))
print("  Innovation gate: {:.1f} (3σ)".format(INNOV_GATE))
print("  Output filter: α {:.3f}(hover)–{:.2f}(motion)".format(ALPHA_HOVER, ALPHA_MOTION))
print("  2nd measurement: altitude rate, R_vel {:.2f}–{:.1f}".format(R_VEL_HOVER, R_VEL_MOTION))

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("\nShutting down...")
    output_file.close()
    vehicle.close()