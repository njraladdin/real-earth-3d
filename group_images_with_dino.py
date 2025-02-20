import torch
from PIL import Image
from pathlib import Path
import shutil
from collections import defaultdict
import numpy as np
from torchvision import transforms
from sklearn.cluster import DBSCAN
import torch.nn.functional as F

def load_dino_model():
    """Load DINO v2 model"""
    model = torch.hub.load('facebookresearch/dinov2', 'dinov2_vits14')
    model.eval()
    if torch.cuda.is_available():
        model = model.cuda()
    return model

def extract_features(image_path, model):
    """Extract DINO features from the image"""
    # Load and preprocess image
    image = Image.open(image_path).convert('RGB')
    transform = transforms.Compose([
        transforms.Resize(256),
        transforms.CenterCrop(224),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], 
                           std=[0.229, 0.224, 0.225])
    ])
    img = transform(image).unsqueeze(0)
    if torch.cuda.is_available():
        img = img.cuda()
    
    # Get features
    with torch.no_grad():
        features = model(img)  # Get global features directly
    
    return features.cpu().numpy()[0]

def compute_similarity(features1, features2):
    """Compute cosine similarity between two feature vectors"""
    f1_norm = F.normalize(torch.tensor(features1).unsqueeze(0), dim=1)
    f2_norm = F.normalize(torch.tensor(features2).unsqueeze(0), dim=1)
    return torch.mm(f1_norm, f2_norm.t()).item()

def group_images_by_objects(input_path, output_path, similarity_threshold=0.8):
    """Group images based on object similarity using DINO features"""
    input_path = Path(input_path)
    output_path = Path(output_path)
    
    # Clear output directory
    if output_path.exists():
        shutil.rmtree(output_path)
    output_path.mkdir(parents=True)
    
    # Load DINO model
    print("Loading DINO model...")
    model = load_dino_model()
    
    # Get all images
    image_files = list(input_path.glob('*.[jJ][pP][gG]')) + \
                 list(input_path.glob('*.[pP][nN][gG]'))
    
    print(f"Processing {len(image_files)} images...")
    
    # Extract features for all images
    image_features = {}
    for img_path in image_files:
        print(f"Extracting features for {img_path.name}")
        features = extract_features(img_path, model)
        image_features[img_path] = features
    
    # Compute similarity matrix
    n_images = len(image_files)
    similarity_matrix = np.zeros((n_images, n_images))
    
    print("\nComputing image similarities...")
    for i in range(n_images):
        for j in range(i+1, n_images):
            sim = compute_similarity(
                image_features[image_files[i]], 
                image_features[image_files[j]]
            )
            similarity_matrix[i, j] = sim
            similarity_matrix[j, i] = sim
            if sim > similarity_threshold:
                print(f"High similarity ({sim:.3f}) between:")
                print(f"  - {image_files[i].name}")
                print(f"  - {image_files[j].name}")
    
    # Cluster images using DBSCAN
    clustering = DBSCAN(
        eps=1-similarity_threshold,
        min_samples=2,
        metric='precomputed'
    ).fit(1 - similarity_matrix)
    
    # Group images by cluster
    groups = defaultdict(list)
    for img_path, label in zip(image_files, clustering.labels_):
        if label >= 0:  # Ignore noise points (-1)
            groups[label].append(img_path)
    
    # Copy images to group folders
    print("\nCopying images to group folders...")
    for group_id, group_images in groups.items():
        group_dir = output_path / f"group_{group_id}"
        group_dir.mkdir(exist_ok=True)
        
        print(f"\nGroup {group_id}: {len(group_images)} images")
        for img_path in group_images:
            dst = group_dir / img_path.name
            shutil.copy2(img_path, dst)
            print(f"  Copied {img_path.name}")
    
    # Report isolated images
    isolated = [img for img, label in zip(image_files, clustering.labels_) 
                if label == -1]
    if isolated:
        print(f"\nFound {len(isolated)} images with no matches:")
        for img in isolated:
            print(f"  {img.name}")
    
    print(f"\nImages grouped into {len(groups)} categories")
    print(f"Results saved in: {output_path}")
    
    return groups

if __name__ == "__main__":
    dataset_path = Path("dataset")
    input_path = dataset_path / "images"
    output_path = dataset_path / "grouped_images_dino"
    
    if not input_path.exists():
        print(f"Error: Input directory not found: {input_path}")
        exit(1)
    
    try:
        group_images_by_objects(input_path, output_path)
    except Exception as e:
        import traceback
        print(f"Error: {e}")
        print(traceback.format_exc())
        exit(1) 