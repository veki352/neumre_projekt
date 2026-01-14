import json
import glob
import os
import numpy as np
import pandas as pd

# ---------------- CONFIG ----------------
JSON_DIR = "openpose_json/video5"
OUTPUT_BVH = "output/video5.bvh"
FPS = 30
NUM_KEYPOINTS = 25
CONF_THRESHOLD = 0.1
SMOOTH_WINDOW = 5
SCALE = 0.01  # pixels -> Blender units
Z_OFFSET = 0.05
# ----------------------------------------

# BODY_25 skeleton (parent index)
SKELETON = {
    8:  -1,  # MidHip (root)
    1:   8,  # Neck
    0:   1,  # Nose
    2:   1,  # RShoulder
    3:   2,
    4:   3,
    5:   1,  # LShoulder
    6:   5,
    7:   6,
    9:   8,  # RHip
    10:  9,
    11: 10,
    12:  8,  # LHip
    13: 12,
    14: 13,
}

# ---------------- UTILS ----------------
def load_frames():
    files = sorted(glob.glob(os.path.join(JSON_DIR, "*_keypoints.json")))
    frames = []

    for f in files:
        with open(f) as fp:
            data = json.load(fp)

        if not data["people"]:
            frames.append(np.full((NUM_KEYPOINTS, 3), np.nan))
            continue

        kp = np.array(data["people"][0]["pose_keypoints_2d"]).reshape(NUM_KEYPOINTS, 3)
        frames.append(kp)

    return np.stack(frames)

def preprocess(data):
    # Remove low confidence keypoints
    data[data[:, :, 2] < CONF_THRESHOLD] = np.nan

    # Interpolate and smooth
    for kp in range(NUM_KEYPOINTS):
        for d in range(2):
            s = pd.Series(data[:, kp, d])
            s = s.interpolate(limit_direction="both")
            s = s.rolling(SMOOTH_WINDOW, center=True, min_periods=1).mean()
            s = s.bfill().ffill()
            data[:, kp, d] = s

    return data

def compute_offsets(data):
    offsets = {}
    first_frame = data[0]
    for j in SKELETON:
        parent = SKELETON[j]
        if parent == -1:
            offsets[j] = np.array([0, 0, Z_OFFSET])
        else:
            child_pos = first_frame[j, :2]
            parent_pos = first_frame[parent, :2]
            if np.any(np.isnan(child_pos)) or np.any(np.isnan(parent_pos)):
                offsets[j] = np.array([0, 0, Z_OFFSET])
            else:
                offsets[j] = np.array([
                    (child_pos[0]-parent_pos[0])*SCALE,
                    -(child_pos[1]-parent_pos[1])*SCALE,
                    Z_OFFSET
                ])
    return offsets

def vector_to_euler(p1, p2):
    """Approximate ZXY Euler angles in degrees for a vector from p1->p2"""
    delta = p2 - p1
    dx, dy, dz = delta
    if np.isnan(dx) or np.isnan(dy):
        return 0.0, 0.0, 0.0
    # 2D rotation in XY plane
    z_rot = np.degrees(np.arctan2(dy, dx))
    x_rot = 0.0
    y_rot = 0.0
    return z_rot, x_rot, y_rot

# ---------------- WRITE BVH ----------------
def write_bvh(data, out_file):
    os.makedirs(os.path.dirname(out_file), exist_ok=True)
    joints = list(SKELETON.keys())
    joint_names = {j: f"J{j}" for j in joints}
    offsets = compute_offsets(data)

    with open(out_file, "w") as f:
        f.write("HIERARCHY\n")
        f.write("ROOT Hips\n{\n")
        f.write(f"  OFFSET {offsets[8][0]:.5f} {offsets[8][1]:.5f} {offsets[8][2]:.5f}\n")
        f.write("  CHANNELS 6 Xposition Yposition Zposition Zrotation Xrotation Yrotation\n")

        def write_joint(j, indent="  "):
            for child, parent in SKELETON.items():
                if parent == j:
                    name = joint_names[child]
                    f.write(f"{indent}JOINT {name}\n")
                    f.write(f"{indent}{{\n")
                    f.write(f"{indent}  OFFSET {offsets[child][0]:.5f} {offsets[child][1]:.5f} {offsets[child][2]:.5f}\n")
                    f.write(f"{indent}  CHANNELS 3 Zrotation Xrotation Yrotation\n")
                    write_joint(child, indent + "  ")
                    f.write(f"{indent}}}\n")

        write_joint(8, "  ")
        f.write("}\n")

        # MOTION
        f.write("MOTION\n")
        f.write(f"Frames: {data.shape[0]}\n")
        f.write(f"Frame Time: {1.0 / FPS:.6f}\n")

        for frame in range(data.shape[0]):
            root_x = data[frame, 8, 0] * SCALE if not np.isnan(data[frame, 8, 0]) else 0
            root_y = -data[frame, 8, 1] * SCALE if not np.isnan(data[frame, 8, 1]) else 0
            root_z = Z_OFFSET
            line = f"{root_x:.5f} {root_y:.5f} {root_z:.5f} 0 0 0"

            for j in joints:
                if j == 8:
                    continue
                parent = SKELETON[j]
                p1 = np.array([
                    data[frame, parent, 0]*SCALE if not np.isnan(data[frame, parent, 0]) else 0,
                    -data[frame, parent, 1]*SCALE if not np.isnan(data[frame, parent, 1]) else 0,
                    Z_OFFSET
                ])
                p2 = np.array([
                    data[frame, j, 0]*SCALE if not np.isnan(data[frame, j, 0]) else 0,
                    -data[frame, j, 1]*SCALE if not np.isnan(data[frame, j, 1]) else 0,
                    Z_OFFSET
                ])
                z, x, y = vector_to_euler(p1, p2)
                line += f" {z:.2f} {x:.2f} {y:.2f}"

            f.write(line + "\n")

    print(f"BVH saved: {out_file}")

# ---------------- MAIN ----------------
def main():
    data = load_frames()
    data = preprocess(data)
    write_bvh(data, OUTPUT_BVH)

if __name__ == "__main__":
    main()
