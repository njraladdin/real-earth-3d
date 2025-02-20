import torch
from PIL import Image
import numpy as np
from collections import defaultdict
from pathlib import Path
import shutil
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.metrics.pairwise import cosine_similarity
import clip  # New import

def group_images_by_content(input_path, output_path, n_clusters=4, min_group_size=1):
    """
    Group images by their main content using CLIP
    """
    # Clear previous output directory if it exists
    if output_path.exists():
        print(f"Clearing previous output directory: {output_path}")
        shutil.rmtree(output_path)
    
    output_path.mkdir(exist_ok=True, parents=True)
    
    print("Loading CLIP model...")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    if device == "cpu":
        print("WARNING: CUDA is not available! This will be much slower.")
    else:
        print(f"Found {torch.cuda.device_count()} CUDA device(s)")
        print(f"Current device: {torch.cuda.get_device_name()}")
    
    # Load CLIP model
    model, preprocess = clip.load("ViT-L/14", device=device)
    
    # Dictionary to store feature vectors for each image
    image_features = {}
    
    # Get list of image files
    image_files = list(input_path.glob('*.[jJ][pP][gG]')) + \
                 list(input_path.glob('*.[pP][nN][gG]'))
    
    if not image_files:
        print(f"No images found in {input_path}")
        return
    
    print(f"Found {len(image_files)} images")
    print("Extracting features from images...")
    
    # Extract features for each image
    batch_size = 8  # Process multiple images at once for speed
    for i in range(0, len(image_files), batch_size):
        batch_files = image_files[i:i + batch_size]
        try:
            # Process batch of images
            images = [Image.open(img_path).convert('RGB') for img_path in batch_files]
            image_inputs = torch.stack([preprocess(img) for img in images]).to(device)
            
            with torch.no_grad():
                # Get image features using CLIP
                features = model.encode_image(image_inputs)
                features = features.cpu().numpy()
                
                # Store features for each image
                for idx, img_path in enumerate(batch_files):
                    print(f"Processing {img_path.name}...")
                    image_features[str(img_path)] = features[idx]
            
        except Exception as e:
            print(f"Error processing batch starting with {batch_files[0]}: {e}")
            continue
    
    if not image_features:
        print("No images were successfully processed!")
        return
    
    print("\nClustering images...")
    
    # Convert features to array for clustering
    paths = list(image_features.keys())
    feature_array = np.array([image_features[p] for p in paths])
    
    # Normalize features
    scaler = StandardScaler()
    feature_array = scaler.fit_transform(feature_array)
    
    # Initial clustering
    n_clusters = min(n_clusters, len(feature_array))
    kmeans = KMeans(n_clusters=n_clusters, n_init=10)
    clusters = kmeans.fit_predict(feature_array)
    
    # Group images by cluster
    grouped_images = defaultdict(list)
    for path, cluster_id in zip(paths, clusters):
        grouped_images[cluster_id].append(Path(path))
    
    # Merge small groups
    if min_group_size > 1:
        cluster_centers = kmeans.cluster_centers_
        small_groups = [k for k, v in grouped_images.items() if len(v) < min_group_size]
        large_groups = [k for k, v in grouped_images.items() if len(v) >= min_group_size]
        
        if small_groups and large_groups:
            print(f"\nMerging {len(small_groups)} small groups...")
            
            for small_group in small_groups:
                if not large_groups:
                    break
                
                # Find closest large group using cosine similarity
                small_group_center = cluster_centers[small_group]
                similarities = [
                    (large_group, cosine_similarity(
                        small_group_center.reshape(1, -1),
                        cluster_centers[large_group].reshape(1, -1)
                    )[0][0])
                    for large_group in large_groups
                ]
                closest_large_group = max(similarities, key=lambda x: x[1])[0]
                
                # Merge small group into closest large group
                grouped_images[closest_large_group].extend(grouped_images[small_group])
                del grouped_images[small_group]
                print(f"Merged group {small_group} into group {closest_large_group}")
    
    print("\nCopying images to group folders...")
    
    # Create subdirectories for each group and copy images
    for cluster_id, images in grouped_images.items():
        group_dir = output_path / f"group_{cluster_id}"
        group_dir.mkdir(exist_ok=True)
        
        print(f"\nGroup {cluster_id}: {len(images)} images")
        
        # Copy images to their group directories
        for img_path in images:
            dst = group_dir / img_path.name
            shutil.copy2(str(img_path), str(dst))
            print(f"  Copied {img_path.name}")
    
    print(f"\nImages grouped into {len(grouped_images)} categories")
    print(f"Results saved in: {output_path}")
    
    return grouped_images

if __name__ == "__main__":
    dataset_path = Path("dataset")
    input_path = dataset_path / "images"
    output_path = dataset_path / "grouped_images"
    
    if not input_path.exists():
        print(f"Error: Input directory not found: {input_path}")
        exit(1)
    
    try:
        group_images_by_content(input_path, output_path)
    except Exception as e:
        import traceback
        print(f"Error: {e}")
        print(traceback.format_exc())
        exit(1) 