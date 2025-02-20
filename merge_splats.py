import numpy as np
from pathlib import Path
import argparse
from datetime import datetime
import struct
from sklearn.neighbors import NearestNeighbors

def read_ply_header(file):
    """Read PLY header and return format, elements and properties"""
    header = []
    while True:
        line = file.readline().decode('ascii').strip()
        header.append(line)
        if line == 'end_header':
            break
    return header

def parse_property_type(type_str):
    """Convert PLY property type string to corresponding struct format"""
    type_map = {
        'float': 'f',
        'float32': 'f',
        'double': 'd',
        'float64': 'd',
        'uchar': 'B',
        'uint8': 'B',
        'uint': 'I',
        'uint32': 'I',
    }
    return type_map.get(type_str, 'f')

def normalize_points(points):
    """Normalize points to have zero mean and unit scale"""
    centroid = np.mean(points, axis=0)
    centered = points - centroid
    scale = np.max(np.abs(centered))
    normalized = centered / scale
    return normalized, centroid, scale

def find_transformation_matrix(source_points, target_points, max_iterations=50, tolerance=1e-6):
    """
    Implement ICP (Iterative Closest Point) algorithm to find transformation matrix
    that aligns source points to target points, including scale
    """
    # Normalize both point clouds first
    source_normalized, source_centroid, source_scale = normalize_points(source_points)
    target_normalized, target_centroid, target_scale = normalize_points(target_points)
    
    print(f"Source scale: {source_scale}, Target scale: {target_scale}")
    
    # Initial scale is the ratio of original scales
    global_scale = target_scale / source_scale
    print(f"Global scale: {global_scale}")
    
    # Initialize transformation matrix
    transformation = np.eye(4)
    prev_error = float('inf')
    
    # Create KD-tree for normalized target points
    nbrs = NearestNeighbors(n_neighbors=1, algorithm='auto').fit(target_normalized)
    
    source_points = source_normalized.copy()
    
    for iteration in range(max_iterations):
        # Find nearest neighbors
        distances, indices = nbrs.kneighbors(source_points)
        corresponding_points = target_normalized[indices.flatten()]
        
        # Calculate centroids
        source_centroid = np.mean(source_points, axis=0)
        target_centroid = np.mean(corresponding_points, axis=0)
        
        # Center the point clouds
        centered_source = source_points - source_centroid
        centered_target = corresponding_points - target_centroid
        
        # Calculate rotation using SVD
        H = centered_source.T @ centered_target
        U, _, Vt = np.linalg.svd(H)
        R = Vt.T @ U.T
        
        # Ensure right-handed coordinate system
        if np.linalg.det(R) < 0:
            Vt[-1,:] *= -1
            R = Vt.T @ U.T
        
        # Calculate translation
        t = target_centroid - (R @ source_centroid)
        
        # Update transformation
        current_transformation = np.eye(4)
        current_transformation[:3, :3] = R
        current_transformation[:3, 3] = t
        
        # Apply transformation
        source_points = (R @ source_points.T).T + t
        
        # Calculate error
        current_error = np.mean(distances)
        
        # Check for convergence
        if abs(prev_error - current_error) < tolerance:
            break
        
        prev_error = current_error
        transformation = current_transformation @ transformation
        
        if iteration % 10 == 0:
            print(f"ICP iteration {iteration}, error: {current_error}")
    
    # Create final transformation that includes the global scale
    final_transformation = np.eye(4)
    final_transformation[:3, :3] = global_scale * transformation[:3, :3]
    final_transformation[:3, 3] = target_centroid * target_scale - (global_scale * transformation[:3, :3] @ source_centroid) * source_scale
    
    return final_transformation

def apply_transformation(points_data, transformation, scale_properties=True):
    """
    Apply transformation matrix to points and scale Gaussian properties
    """
    # Extract positions (first 3 columns)
    positions = points_data[:, :3]
    
    # Convert positions to homogeneous coordinates
    homogeneous = np.hstack([positions, np.ones((len(positions), 1))])
    
    # Apply transformation to positions
    transformed = (transformation @ homogeneous.T).T
    transformed_positions = transformed[:, :3]
    
    # Create output array
    result = points_data.copy()
    result[:, :3] = transformed_positions
    
    if scale_properties:
        # Extract scale from transformation matrix (average of diagonal elements)
        scale = np.mean(np.abs(np.diag(transformation[:3, :3])))
        
        # Scale the Gaussian properties
        # Format: [x, y, z, scale_x, scale_y, scale_z, rot_x, rot_y, rot_z, opacity]
        
        # Scale the scale components (columns 3,4,5) more conservatively
        scale_factor = np.sqrt(scale)  # Use square root of scale to be more conservative
        result[:, 3:6] *= scale_factor
        
        # Don't modify rotation components (6,7,8)
        
        # Adjust opacity (column 9) to maintain density
        density_factor = 1.0 / scale_factor
        result[:, -1] = np.clip(result[:, -1] * density_factor, 0.1, 1.0)  # Keep minimum opacity
    
    return result

def visualize_points(points1, points2, title="Point Clouds"):
    """Visualize two point clouds"""
    try:
        import matplotlib.pyplot as plt
        from mpl_toolkits.mplot3d import Axes3D
        
        fig = plt.figure(figsize=(10, 10))
        ax = fig.add_subplot(111, projection='3d')
        
        # Plot first point cloud in blue
        ax.scatter(points1[:, 0], points1[:, 1], points1[:, 2], c='blue', s=1, alpha=0.5, label='Splat 1')
        
        # Plot second point cloud in red
        ax.scatter(points2[:, 0], points2[:, 1], points2[:, 2], c='red', s=1, alpha=0.5, label='Splat 2')
        
        ax.set_title(title)
        ax.legend()
        
        # Save the plot
        plt.savefig(f"recent_splats/{title.lower().replace(' ', '_')}.png")
        plt.close()
    except ImportError:
        print("Matplotlib not available for visualization")

def merge_splats(splat1_path, splat2_path, output_dir=None, alignment_sample_size=5000):
    """
    Merge two splat PLY files while preserving all properties
    
    Args:
        splat1_path (str): Path to first splat file
        splat2_path (str): Path to second splat file
        output_dir (str): Directory to save merged splat
        alignment_sample_size (int): Number of points to use for alignment
    """
    # Prepare output directory
    if output_dir is None:
        output_dir = Path("recent_splats")
    else:
        output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)
    
    # Read first splat file header
    with open(splat1_path, 'rb') as f1:
        header1 = read_ply_header(f1)
        data_start1 = f1.tell()
    
    # Parse header to get property types and count
    properties = []
    vertex_count = 0
    for line in header1:
        if line.startswith('element vertex'):
            vertex_count = int(line.split()[-1])
        elif line.startswith('property'):
            parts = line.split()
            prop_type = parse_property_type(parts[1])
            properties.append((parts[-1], prop_type))
    
    # Create struct format for reading/writing
    struct_format = '<' + ''.join(p[1] for p in properties)
    struct_size = struct.calcsize(struct_format)
    
    # Read data from both files
    def read_splat_data(filepath):
        with open(filepath, 'rb') as f:
            read_ply_header(f)  # Skip header
            data = []
            while True:
                chunk = f.read(struct_size)
                if not chunk:
                    break
                if len(chunk) < struct_size:
                    break
                values = struct.unpack(struct_format, chunk)
                data.append(values)
        return np.array(data)
    
    print("Reading splat files...")
    data1 = read_splat_data(splat1_path)
    data2 = read_splat_data(splat2_path)
    
    print(f"Points in splat1: {len(data1)}")
    print(f"Points in splat2: {len(data2)}")
    
    # Extract positions for alignment
    positions1 = data1[:, :3]
    positions2 = data2[:, :3]
    
    # Visualize before alignment
    visualize_points(positions1, positions2, "Before Alignment")
    
    # Print bounding box info for debugging
    bbox1 = np.ptp(positions1, axis=0)
    bbox2 = np.ptp(positions2, axis=0)
    print(f"Splat1 bounding box size: {bbox1}")
    print(f"Splat2 bounding box size: {bbox2}")
    
    print("Aligning splats...")
    # Sample points for faster alignment
    if len(positions1) > alignment_sample_size:
        indices1 = np.random.choice(len(positions1), alignment_sample_size, replace=False)
        indices2 = np.random.choice(len(positions2), alignment_sample_size, replace=False)
        sample_positions1 = positions1[indices1]
        sample_positions2 = positions2[indices2]
    else:
        sample_positions1 = positions1
        sample_positions2 = positions2
    
    # Find transformation to align splat2 to splat1
    transformation = find_transformation_matrix(sample_positions2, sample_positions1)
    
    # Apply transformation to all points in data2, including Gaussian properties
    print("Applying transformation...")
    transformed_data2 = apply_transformation(data2, transformation, scale_properties=True)
    
    # Visualize after alignment (still using only positions)
    visualize_points(positions1, transformed_data2[:, :3], "After Alignment")
    
    # Combine data
    print("Merging splats...")
    combined_data = np.vstack([data1, transformed_data2])
    print(f"Total points in merged splat: {len(combined_data)}")
    
    # Save merged result
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = output_dir / f"merged_splat_{timestamp}.ply"
    
    print(f"Saving merged splat to: {output_path}")
    with open(output_path, 'wb') as f:
        # Write header
        f.write(b'ply\n')
        f.write(b'format binary_little_endian 1.0\n')
        f.write(f'element vertex {len(combined_data)}\n'.encode())
        for prop_name, _ in properties:
            f.write(f'property float {prop_name}\n'.encode())
        f.write(b'end_header\n')
        
        # Write data
        for row in combined_data:
            f.write(struct.pack(struct_format, *row))
    
    return str(output_path)

def main():
    parser = argparse.ArgumentParser(description="Merge two splat PLY files")
    parser.add_argument("--splat1", default="recent_splats/splat1.ply",
                      help="Path to first splat PLY file (default: recent_splats/splat1.ply)")
    parser.add_argument("--splat2", default="recent_splats/splat2.ply",
                      help="Path to second splat PLY file (default: recent_splats/splat2.ply)")
    parser.add_argument("--output-dir", default="recent_splats",
                      help="Output directory for merged splat (default: recent_splats)")
    parser.add_argument("--alignment-sample-size", type=int, default=5000,
                      help="Number of points to use for alignment (default: 5000)")
    
    args = parser.parse_args()
    
    # Check if default files exist
    if not Path(args.splat1).exists():
        print(f"Error: {args.splat1} not found")
        return 1
    if not Path(args.splat2).exists():
        print(f"Error: {args.splat2} not found")
        return 1
    
    try:
        output_path = merge_splats(
            args.splat1,
            args.splat2,
            args.output_dir,
            args.alignment_sample_size
        )
        print(f"Successfully merged splats to: {output_path}")
    except Exception as e:
        print(f"Error merging splats: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main()) 