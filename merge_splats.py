import numpy as np
from pathlib import Path
import re

def read_cameras_text(path):
    """Read cameras.txt file"""
    cameras = {}
    with open(path, "r") as f:
        for line in f:
            if line[0] == "#":  # Skip comments
                continue
            data = line.strip().split()
            if len(data) == 0:  # Skip empty lines
                continue
            camera_id = int(data[0])
            model = data[1]
            width = int(data[2])
            height = int(data[3])
            params = np.array(data[4:], dtype=np.float64)
            cameras[camera_id] = {
                "model": model,
                "width": width,
                "height": height,
                "params": params
            }
    return cameras

def read_images_text(path):
    """Read images.txt file"""
    images = {}
    with open(path, "r") as f:
        while True:
            line = f.readline()
            if not line:
                break
            if line[0] == "#":  # Skip comments
                continue
            data = line.strip().split()
            if len(data) == 0:  # Skip empty lines
                continue
                
            # Read image data
            image_id = int(data[0])
            qw, qx, qy, qz = map(float, data[1:5])
            tx, ty, tz = map(float, data[5:8])
            camera_id = int(data[8])
            name = data[9]
            
            # Read points data from next line
            points_line = f.readline().strip().split()
            points2D = []
            for i in range(0, len(points_line), 3):
                x = float(points_line[i])
                y = float(points_line[i + 1])
                point3D_id = int(points_line[i + 2])
                points2D.append((x, y, point3D_id))
            
            images[image_id] = {
                "quaternion": np.array([qw, qx, qy, qz]),
                "translation": np.array([tx, ty, tz]),
                "camera_id": camera_id,
                "name": name,
                "points2D": points2D
            }
    return images

def read_points3D_text(path):
    """Read points3D.txt file"""
    points3D = {}
    with open(path, "r") as f:
        for line in f:
            if line[0] == "#":  # Skip comments
                continue
            data = line.strip().split()
            if len(data) == 0:  # Skip empty lines
                continue
            
            point3D_id = int(data[0])
            xyz = np.array(data[1:4], dtype=np.float64)
            rgb = np.array(data[4:7], dtype=np.uint8)
            error = float(data[7])
            track = np.array(data[8:], dtype=np.int64).reshape(-1, 2)
            
            points3D[point3D_id] = {
                "xyz": xyz,
                "rgb": rgb,
                "error": error,
                "track": track
            }
    return points3D

def write_cameras_text(cameras, path):
    """Write cameras to cameras.txt"""
    with open(path, "w") as f:
        f.write("# Camera list with one line of data per camera:\n")
        f.write("#   CAMERA_ID, MODEL, WIDTH, HEIGHT, PARAMS[]\n")
        for camera_id, camera in cameras.items():
            params_str = " ".join(map(str, camera["params"]))
            f.write(f"{camera_id} {camera['model']} {camera['width']} {camera['height']} {params_str}\n")

def write_images_text(images, path):
    """Write images to images.txt"""
    with open(path, "w") as f:
        f.write("# Image list with two lines of data per image:\n")
        f.write("#   IMAGE_ID, QW, QX, QY, QZ, TX, TY, TZ, CAMERA_ID, NAME\n")
        f.write("#   POINTS2D[] as (X, Y, POINT3D_ID)\n")
        for image_id, image in images.items():
            quat = " ".join(map(str, image["quaternion"]))
            trans = " ".join(map(str, image["translation"]))
            f.write(f"{image_id} {quat} {trans} {image['camera_id']} {image['name']}\n")
            
            points_str = []
            for x, y, point3D_id in image["points2D"]:
                points_str.extend([str(x), str(y), str(point3D_id)])
            f.write(" ".join(points_str) + "\n")

def write_points3D_text(points3D, path):
    """Write points3D to points3D.txt"""
    with open(path, "w") as f:
        f.write("# 3D point list with one line of data per point:\n")
        f.write("#   POINT3D_ID, X, Y, Z, R, G, B, ERROR, TRACK[] as (IMAGE_ID, POINT2D_IDX)\n")
        for point3D_id, point3D in points3D.items():
            xyz = " ".join(map(str, point3D["xyz"]))
            rgb = " ".join(map(str, point3D["rgb"]))
            track_str = " ".join(map(str, point3D["track"].flatten()))
            f.write(f"{point3D_id} {xyz} {rgb} {point3D['error']} {track_str}\n")

def merge_colmap_models(model1_path, model2_path, output_path):
    """Merge two COLMAP models"""
    # Read both models
    cameras1 = read_cameras_text(model1_path / "cameras.txt")
    images1 = read_images_text(model1_path / "images.txt")
    points3D1 = read_points3D_text(model1_path / "points3D.txt")
    
    cameras2 = read_cameras_text(model2_path / "cameras.txt")
    images2 = read_images_text(model2_path / "images.txt")
    points3D2 = read_points3D_text(model2_path / "points3D.txt")
    
    print(f"Model 1: {len(cameras1)} cameras, {len(images1)} images, {len(points3D1)} points")
    print(f"Model 2: {len(cameras2)} cameras, {len(images2)} images, {len(points3D2)} points")
    
    # Merge cameras (adjust IDs to avoid conflicts)
    max_camera_id1 = max(cameras1.keys())
    cameras_merged = cameras1.copy()
    for camera_id, camera in cameras2.items():
        new_camera_id = camera_id + max_camera_id1 + 1
        cameras_merged[new_camera_id] = camera
    
    # Merge images (adjust IDs and camera IDs)
    max_image_id1 = max(images1.keys())
    images_merged = images1.copy()
    for image_id, image in images2.items():
        new_image_id = image_id + max_image_id1 + 1
        image_copy = image.copy()
        image_copy["camera_id"] += max_camera_id1 + 1
        images_merged[new_image_id] = image_copy
    
    # Merge points3D (adjust IDs and image IDs in tracks)
    max_point3D_id1 = max(points3D1.keys())
    points3D_merged = points3D1.copy()
    for point3D_id, point3D in points3D2.items():
        new_point3D_id = point3D_id + max_point3D_id1 + 1
        point3D_copy = point3D.copy()
        # Adjust image IDs in track
        point3D_copy["track"][:, 0] += max_image_id1 + 1
        points3D_merged[new_point3D_id] = point3D_copy
    
    # Create output directory
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Write merged model
    write_cameras_text(cameras_merged, output_path / "cameras.txt")
    write_images_text(images_merged, output_path / "images.txt")
    write_points3D_text(points3D_merged, output_path / "points3D.txt")
    
    print(f"Merged model: {len(cameras_merged)} cameras, {len(images_merged)} images, {len(points3D_merged)} points")
    print(f"Saved to: {output_path}")

def main():
    model1_path = Path("dataset_main/sparse")
    model2_path = Path("dataset_staging/sparse")
    output_path = Path("dataset_merged/sparse")
    
    merge_colmap_models(model1_path, model2_path, output_path)

if __name__ == "__main__":
    main()
