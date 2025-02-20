from pathlib import Path
import shutil
from collections import Counter
import torch
from groundingdino.util.inference import load_model, load_image, predict
import numpy as np
from PIL import Image
from torchvision import transforms
import torch.nn.functional as F
from tqdm import tqdm
from sklearn.cluster import DBSCAN
from scipy.cluster.hierarchy import linkage, fcluster
from scipy.spatial.distance import squareform

def load_grounding_dino():
    """Load GroundingDINO model"""
    config_path = "GroundingDINO/groundingdino/config/GroundingDINO_SwinT_OGC.py"
    checkpoint_path = "GroundingDINO/groundingdino_swint_ogc.pth"
    
    if not Path(config_path).exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    if not Path(checkpoint_path).exists():
        raise FileNotFoundError(f"Model checkpoint not found: {checkpoint_path}")
    
    model = load_model(config_path, checkpoint_path)
    model.eval()
    if torch.cuda.is_available():
        model = model.cuda()
    return model


def load_dino_model():
    """Load DINO v2 model"""
    # Using the large variant for better feature extraction
    model = torch.hub.load('facebookresearch/dinov2', 'dinov2_vitb14')
    model.eval()
    if torch.cuda.is_available():
        model = model.cuda()
    return model

def extract_features(image_path, model, transform):
    """Extract DINO features from image"""
    try:
        image = Image.open(image_path).convert('RGB')
        img = transform(image).unsqueeze(0)
        if torch.cuda.is_available():
            img = img.cuda()
        
        with torch.no_grad():
            features = model(img)
        return features.cpu().numpy()[0]
    except Exception as e:
        print(f"Error processing {image_path}: {e}")
        return None

def compute_similarity_matrix(features):
    """Compute pairwise cosine similarity between all features"""
    features = torch.tensor(features)
    features_norm = F.normalize(features, dim=1)
    similarity_matrix = torch.mm(features_norm, features_norm.t())
    # Ensure similarities are between 0 and 1
    similarity_matrix = (similarity_matrix + 1) / 2
    # Double check no negative values due to numerical errors
    similarity_matrix = torch.clamp(similarity_matrix, 0, 1)
    return similarity_matrix.cpu().numpy()

def filter_images(input_folder="initial_images", output_folder=None, removed_folder=None,
                 similarity_threshold=0.85, min_samples=5):
    input_path = Path(input_folder)
    
    # Generate default output and removed folders if not provided
    if output_folder is None:
        output_folder = input_folder + "_filtered"
    if removed_folder is None:
        removed_folder = input_folder + "_removed_by_filtration"
    
    output_path = Path(output_folder)
    removed_path = Path(removed_folder)
    
    # Clear and create output directories
    for path in [output_path, removed_path]:
        if path.exists():
            shutil.rmtree(path)
        path.mkdir(parents=True, exist_ok=True)
    
    # Get all images
    image_files = list(input_path.glob('*.[jJ][pP][gG]')) + \
                 list(input_path.glob('*.[pP][nN][gG]'))
    
    if not image_files:
        print(f"No images found in {input_path}")
        return
    
    print(f"Found {len(image_files)} images")
    
    # Load model
    print("Loading DINO v2 model...")
    model = load_dino_model()
    
    # Define image transform
    transform = transforms.Compose([
        transforms.Resize(256),
        transforms.CenterCrop(224),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], 
                           std=[0.229, 0.224, 0.225])
    ])
    
    # Extract features from all images
    print("Extracting features from images...")
    features_dict = {}
    for img_path in tqdm(image_files):
        features = extract_features(img_path, model, transform)
        if features is not None:
            features_dict[img_path] = features
    
    if not features_dict:
        print("No features could be extracted from images!")
        return
    
    # Compute similarity matrix
    print("Computing similarity matrix...")
    paths = list(features_dict.keys())
    features_array = np.stack([features_dict[p] for p in paths])
    similarity_matrix = compute_similarity_matrix(features_array)
    
    # Convert similarity to distance and ensure symmetry
    distance_matrix = 1 - similarity_matrix
    # Make the matrix symmetric by averaging with its transpose
    distance_matrix = (distance_matrix + distance_matrix.T) / 2
    np.fill_diagonal(distance_matrix, 0)  # ensure self-distance is 0
    
    # Perform hierarchical clustering
    Z = linkage(squareform(distance_matrix), method='ward')
    
    # Cut the dendrogram to get clusters
    max_d = 0.3  # Maximum distance for a cluster
    clusters = fcluster(Z, max_d, criterion='distance')
    
    # Find the largest cluster
    unique_clusters, cluster_sizes = np.unique(clusters, return_counts=True)
    largest_cluster = unique_clusters[np.argmax(cluster_sizes)]
    
    # Get indices of images in largest cluster
    initial_kept_indices = np.where(clusters == largest_cluster)[0]
    
    # Get the mean features of the initial cluster
    cluster_center = np.mean(features_array[initial_kept_indices], axis=0)
    cluster_center = cluster_center / np.linalg.norm(cluster_center)
    
    # Find all images that are similar enough using thresholds
    kept_indices = []
    FINAL_THRESHOLD = 0.7    # Threshold for final score
    MEAN_THRESHOLD = 0.75    # Higher threshold for mean similarity
    MIN_CENTER_THRESHOLD = 0.7  # Minimum required similarity to center
    
    for idx in range(len(features_array)):
        features = features_array[idx]
        features = features / np.linalg.norm(features)
        
        # Compute similarity to cluster center
        sim_to_center = np.dot(features, cluster_center)
        
        # Skip if center similarity is too low
        if sim_to_center < MIN_CENTER_THRESHOLD:
            continue
        
        # Also check similarity to other kept images
        if len(kept_indices) > 0:
            sims_to_kept = [similarity_matrix[idx, k] for k in kept_indices]
            mean_sim_to_kept = np.mean(sims_to_kept)
            # Use average of center similarity and mean similarity to kept images
            sim_score = (sim_to_center + mean_sim_to_kept) / 2
            # Keep if either final score or mean similarity is good enough
            if sim_score > FINAL_THRESHOLD or mean_sim_to_kept > MEAN_THRESHOLD:
                kept_indices.append(idx)
        else:
            sim_score = sim_to_center
            if sim_score > FINAL_THRESHOLD:
                kept_indices.append(idx)
    
    kept_indices = np.array(sorted(kept_indices))
    
    # Print more detailed clustering info
    print("\nClustering information:")
    print(f"Initial cluster size: {len(initial_kept_indices)}")
    print(f"Final cluster size after similarity check: {len(kept_indices)}")
    
    # Copy similar images to output directory and removed images to removed directory
    print("\nCopying images...")
    filtered_count = 0
    removed_count = 0
    
    # Create set of indices to be kept for faster lookup
    kept_indices_set = set(kept_indices)
    
    # Calculate cluster statistics
    cluster_similarities = similarity_matrix[kept_indices][:, kept_indices]
    avg_cluster_similarity = np.mean(cluster_similarities)
    min_cluster_similarity = np.min(cluster_similarities)
    
    # Process all images
    for idx, src in enumerate(paths):
        # Calculate similarities
        sim_to_center = np.dot(features_array[idx] / np.linalg.norm(features_array[idx]), cluster_center)
        mean_sim_to_kept = np.mean(similarity_matrix[idx, list(kept_indices_set - {idx})] if idx in kept_indices_set else similarity_matrix[idx, list(kept_indices_set)])
        final_score = (sim_to_center + mean_sim_to_kept) / 2

        if idx in kept_indices_set:
            dst = output_path / src.name
            shutil.copy2(src, dst)
            filtered_count += 1
            print(f"Kept {src.name} (center: {sim_to_center:.3f}, mean: {mean_sim_to_kept:.3f}, final: {final_score:.3f})")
        else:
            dst = removed_path / src.name
            shutil.copy2(src, dst)
            removed_count += 1
            print(f"Removed {src.name} (center: {sim_to_center:.3f}, mean: {mean_sim_to_kept:.3f}, final: {final_score:.3f})")
    
    print(f"\nResults:")
    print(f"- Original images: {len(image_files)}")
    print(f"- Filtered images: {filtered_count}")
    print(f"- Removed images: {removed_count}")
    print(f"- Average similarity within kept cluster: {avg_cluster_similarity:.3f}")
    print(f"- Minimum similarity within kept cluster: {min_cluster_similarity:.3f}")
    print(f"\nKept images saved to: {output_path}")
    print(f"Removed images saved to: {removed_path}")

if __name__ == "__main__":
    try:
        filter_images(input_folder="initial_images")
    except Exception as e:
        import traceback
        print(f"Error: {e}")
        print(traceback.format_exc())
        exit(1) 