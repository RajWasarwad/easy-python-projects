import numpy as np
from collections import deque

class MedianFilter:
    def __init__(self, window_size=5):
        # A window size of 3 or 5 is usually perfect for IMU spikes
        self.window = deque(maxlen=window_size)

    def update(self, new_value):
        self.window.append(new_value)
        # Return the median of the current window
        return np.median(self.window)

# --- Usage in your loop ---
# accel_z_filter = MedianFilter(window_size=5)
# clean_accel = accel_z_filter.update(raw_imu_accel_z)
# ekf.predict(clean_accel, dt)



def ekf_update_with_gating(x, P, z, H, R, gate_threshold=3.0):
    """
    x: State vector
    P: State covariance matrix
    z: Measurement (e.g., altitude)
    H: Observation matrix
    R: Measurement noise matrix
    gate_threshold: 3.0 means reject anything outside 3 standard deviations
    """
    # 1. Predict measurement from current state
    z_pred = H @ x

    # 2. Calculate Innovation (y) and Innovation Covariance (S)
    y = z - z_pred
    S = H @ P @ H.T + R

    # 3. 3-Sigma Gating Check
    # For a 1D measurement like altitude, extract the scalar values
    S_scalar = S[0, 0] if isinstance(S, np.ndarray) else S
    y_scalar = y[0] if isinstance(y, np.ndarray) else y
    
    std_dev = np.sqrt(S_scalar)

    # Check if the error is larger than expected
    if abs(y_scalar) > gate_threshold * std_dev:
        # SPIKE DETECTED: Reject the measurement.
        # Return the un-updated state (trust the IMU prediction only for this step)
        return x, P, True # True indicates rejection

    # 4. Standard EKF Update (if the gate passes)
    K = P @ H.T @ np.linalg.inv(S)
    x = x + K @ y
    
    # Joseph form update for numerical stability
    I = np.eye(len(x))
    P = (I - K @ H) @ P @ (I - K @ H).T + K @ R @ K.T

    return x, P, False






class KinematicRateLimiter:
    def __init__(self, max_acceleration_g=3.0, dt=0.01):
        """
        max_acceleration_g: The maximum thrust capability of your drone in Gs.
        dt: Your EKF loop time step.
        """
        # Convert Gs to m/s^2 (e.g., 3G = ~29.4 m/s^2)
        self.max_accel_ms2 = max_acceleration_g * 9.81
        self.dt = dt
        self.prev_vz = None

    def limit(self, current_vz):
        if self.prev_vz is None:
            self.prev_vz = current_vz
            return current_vz

        # The maximum velocity change physically possible in one time step
        max_delta_v = self.max_accel_ms2 * self.dt

        # Calculate the requested velocity change from the EKF
        delta_v = current_vz - self.prev_vz
        
        # Clamp the change to physical reality
        delta_v = np.clip(delta_v, -max_delta_v, max_delta_v)

        # Output the safely clamped velocity
        clamped_vz = self.prev_vz + delta_v
        self.prev_vz = clamped_vz

        return clamped_vz

# --- Usage in your loop ---
# vz_limiter = KinematicRateLimiter(max_acceleration_g=3.0, dt=0.01)
# safe_vz = vz_limiter.limit(ekf_vz_output)