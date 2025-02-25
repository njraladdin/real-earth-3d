from pathlib import Path
import shutil
import torch
from PIL import Image
from torchvision import transforms
import torch.nn.functional as F
import numpy as np
from tqdm import tqdm

def load_dino_model():
    """Load DINO v2 model"""
    model = torch.hub.load('facebookresearch/dinov2', 'dinov2_vitl14')
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

def compute_similarity(features1, features2):
    """Compute cosine similarity between two feature vectors"""
    features1_norm = features1 / np.linalg.norm(features1)
    features2_norm = features2 / np.linalg.norm(features2)
    return np.dot(features1_norm, features2_norm)

def remove_similar_images(
    input_folder="initial_images_filtered",
    output_folder="initial_images_deduplicated",
    removed_folder="initial_images_duplicates",
    similarity_threshold=0.98  # Increased from 0.95 to 0.98 to be more conservative
):
    input_path = Path(input_folder)
    output_path = Path(output_folder)
    removed_path = Path(removed_folder)
    
    # Create output directories
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
    
    # Find duplicate groups
    duplicate_groups = []
    processed = set()
    
    print("Finding duplicate images...")
    for img_path1, features1 in tqdm(features_dict.items()):
        if img_path1 in processed:
            continue
            
        current_group = [img_path1]
        
        for img_path2, features2 in features_dict.items():
            if img_path2 == img_path1 or img_path2 in processed:
                continue
                
            similarity = compute_similarity(features1, features2)
            if similarity > similarity_threshold:
                current_group.append(img_path2)
                
        if len(current_group) > 1:
            duplicate_groups.append(current_group)
            processed.update(current_group[1:])  # Mark all but the first image as processed
        processed.add(img_path1)
    
    # Copy images to appropriate folders
    print("\nCopying images...")
    kept_count = 0
    removed_count = 0
    
    # First, copy all images that aren't in any duplicate group
    duplicates_flat = {img for group in duplicate_groups for img in group[1:]}
    for img_path in image_files:
        if img_path not in duplicates_flat:
            shutil.copy2(img_path, output_path / img_path.name)
            kept_count += 1
    
    # Then handle duplicate groups
    for group in duplicate_groups:
        # Remove the duplicates
        for img_path in group[1:]:
            shutil.copy2(img_path, removed_path / img_path.name)
            removed_count += 1
            print(f"Removed duplicate: {img_path.name} (similar to {group[0].name})")
    
    print(f"\nResults:")
    print(f"- Original images: {len(image_files)}")
    print(f"- Kept images: {kept_count}")
    print(f"- Removed duplicates: {removed_count}")
    print(f"- Number of duplicate groups found: {len(duplicate_groups)}")
    print(f"\nDeduplicated images saved to: {output_path}")
    print(f"Removed duplicates saved to: {removed_path}")

if __name__ == "__main__":
    try:
        remove_similar_images()
    except Exception as e:
        import traceback
        print(f"Error: {e}")
        print(traceback.format_exc())
        exit(1) 