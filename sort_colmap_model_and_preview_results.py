from pathlib import Path
import numpy as np
from PIL import Image
import matplotlib.pyplot as plt
from matplotlib.offsetbox import OffsetImage, AnnotationBbox

def read_colmap_cameras_positions(sparse_path):
    """Read camera positions from COLMAP reconstruction"""
    images_txt = sparse_path / "images.txt"
    if not images_txt.exists():
        raise FileNotFoundError(f"Could not find {images_txt}")
        
    cameras = []
    with open(images_txt, 'r') as f:
        # Skip header
        while True:
            line = f.readline()
            if not line or not line.startswith('#'):
                break
                
        # Read camera data
        while line:
            if line.strip() and not line.startswith('#'):
                parts = line.strip().split()
                if len(parts) >= 10:  # Image line
                    image_name = parts[-1]
                    tx, ty, tz = map(float, parts[5:8])  # Camera position
                    cameras.append({
                        'name': image_name,
                        'position': np.array([tx, ty, tz])
                    })
                    f.readline()  # Skip points line
            line = f.readline()
            
    return cameras

def create_thumbnail(image_path, max_size=100):
    """Create a thumbnail while maintaining aspect ratio"""
    img = Image.open(image_path)
    img.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
    return img

def plot_cameras_with_thumbnails(cameras, dataset_path, output_path=None, thumbnail_size=100):
    """Plot camera positions with image thumbnails"""
    # Extract positions
    positions = np.array([cam['position'] for cam in cameras])
    
    # Create figure
    plt.figure(figsize=(15, 15))
    
    # Plot camera positions
    plt.scatter(positions[:, 0], positions[:, 1], alpha=0)
    
    # Add thumbnails
    for cam in cameras:
        img_path = dataset_path / "images" / cam['name']
        if img_path.exists():
            # Create and add thumbnail
            thumb = create_thumbnail(img_path, thumbnail_size)
            imagebox = OffsetImage(thumb, zoom=0.5)
            ab = AnnotationBbox(imagebox, (cam['position'][0], cam['position'][1]),
                              frameon=False, pad=0.0)
            plt.gca().add_artist(ab)
    
    plt.title("Camera Positions with Image Thumbnails")
    plt.xlabel("X Position")
    plt.ylabel("Y Position")
    
    # Make axes equal to preserve spatial relationships
    plt.axis('equal')
    
    # Save or show
    if output_path:
        plt.savefig(output_path, bbox_inches='tight', dpi=300)
        print(f"Saved visualization to {output_path}")
    else:
        plt.show()
    
    plt.close()

def main(dataset_path="dataset_staging"):
    """Main function to create visualization"""
    dataset_path = Path(dataset_path)
    sparse_path = dataset_path / "sparse"
    
    print("Reading camera positions from COLMAP reconstruction...")
    cameras = read_colmap_cameras_positions(sparse_path)
    
    if not cameras:
        print("No cameras found in reconstruction!")
        return
        
    print(f"Found {len(cameras)} cameras in reconstruction")
    
    # Create visualization
    print("Creating visualization...")
    output_path = dataset_path / "camera_positions_visualization.png"
    plot_cameras_with_thumbnails(cameras, dataset_path, output_path)
    
if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Error: {e}")
        exit(1) 