import torch
from PIL import Image
from pathlib import Path
import shutil
from collections import defaultdict
import numpy as np
from groundingdino.util.inference import load_model, load_image, predict
from groundingdino.config import GroundingDINO_SwinT_OGC
import torch.nn.functional as F
from sklearn.cluster import DBSCAN

def load_grounding_dino():
    """Load GroundingDINO model"""
    # Get the config path and checkpoint path
    config_path = "GroundingDINO/groundingdino/config/GroundingDINO_SwinT_OGC.py"
    checkpoint_path = "GroundingDINO/groundingdino_swint_ogc.pth"
    
    # Check if files exist
    if not Path(config_path).exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    if not Path(checkpoint_path).exists():
        raise FileNotFoundError(f"Model checkpoint not found: {checkpoint_path}")
    
    # Load model
    model = load_model(config_path, checkpoint_path)
    model.eval()
    if torch.cuda.is_available():
        model = model.cuda()
    return model

def detect_objects(image_path, model, confidence_threshold=0.3):
    """Detect objects in image using GroundingDINO"""
    # Load and preprocess image
    image_source, image = load_image(str(image_path))
    
    # Run detection with empty prompt to detect any objects
    boxes, logits, phrases = predict(
        model=model,
        image=image,
        caption="object . thing . area . structure . pattern . surface . detail",  # Empty prompt for open-ended detection
        box_threshold=confidence_threshold,
        text_threshold=confidence_threshold
    )
    
    objects = []
    if len(boxes) > 0:
        # Convert boxes to normalized coordinates
        H, W = image_source.shape[:2]
        for box, logit, phrase in zip(boxes, logits, phrases):
            x1, y1, x2, y2 = box.cpu().numpy()
            x1, x2 = x1 * W, x2 * W
            y1, y2 = y1 * H, y2 * H
            
            objects.append({
                'box': box.cpu().numpy(),
                'confidence': logit.item(),
                'label': phrase,
                'features': None  # We won't use features
            })
    
    return objects

def compute_object_similarity(obj1, obj2):
    """Compute similarity between two objects based on labels and confidence"""
    # If objects have different labels, return 0 similarity
    if obj1['label'] != obj2['label']:
        return 0.0
    
    # If same label, use the average of confidences to make matching more lenient
    return (obj1['confidence'] + obj2['confidence']) / 2.0

def group_images_by_objects(input_path, output_path, similarity_threshold=0.3):
    """Group images based on detected objects"""
    input_path = Path(input_path)
    output_path = Path(output_path)
    
    if output_path.exists():
        shutil.rmtree(output_path)
    output_path.mkdir(parents=True)
    
    # Load model
    print("Loading GroundingDINO model...")
    model = load_grounding_dino()
    
    # Get all images
    image_files = list(input_path.glob('*.[jJ][pP][gG]')) + \
                 list(input_path.glob('*.[pP][nN][gG]'))
    
    print(f"Processing {len(image_files)} images...")
    
    # Detect objects in all images
    image_objects = {}
    for img_path in image_files:
        print(f"Detecting objects in {img_path.name}")
        objects = detect_objects(img_path, model)
        if objects:
            image_objects[img_path] = objects
            print(f"  Found {len(objects)} objects:")
            for obj in objects:
                print(f"    - {obj['label']} (confidence: {obj['confidence']:.2f})")
    
    # Compute similarity matrix based on shared objects
    n_images = len(image_files)
    similarity_matrix = np.zeros((n_images, n_images))
    
    print("\nComputing image similarities based on objects...")
    for i in range(n_images):
        for j in range(i+1, n_images):
            img1, img2 = image_files[i], image_files[j]
            
            if img1 not in image_objects or img2 not in image_objects:
                continue
            
            # Compare all objects between images
            max_similarity = 0
            for obj1 in image_objects[img1]:
                for obj2 in image_objects[img2]:
                    sim = compute_object_similarity(obj1, obj2)
                    max_similarity = max(max_similarity, sim)
            
            similarity_matrix[i, j] = max_similarity
            similarity_matrix[j, i] = max_similarity
            
            if max_similarity > similarity_threshold:
                print(f"\nHigh object similarity ({max_similarity:.3f}) between:")
                print(f"  - {img1.name}")
                print(f"  - {img2.name}")
                print("  Matching objects:")
                for obj1 in image_objects[img1]:
                    for obj2 in image_objects[img2]:
                        sim = compute_object_similarity(obj1, obj2)
                        if sim > similarity_threshold:
                            print(f"    {obj1['label']} <-> {obj2['label']}: {sim:.3f}")
    
    # Cluster images using DBSCAN
    clustering = DBSCAN(
        eps=1-similarity_threshold,
        min_samples=2,
        metric='precomputed'
    ).fit(1 - similarity_matrix)
    
    # Group images by cluster
    groups = defaultdict(list)
    for img_path, label in zip(image_files, clustering.labels_):
        if label >= 0:
            groups[label].append(img_path)
    
    # Copy images to group folders
    print("\nCopying images to group folders...")
    for group_id, group_images in groups.items():
        group_dir = output_path / f"group_{group_id}"
        group_dir.mkdir(exist_ok=True)
        
        print(f"\nGroup {group_id}: {len(group_images)} images")
        print("Common objects in group:")
        group_objects = defaultdict(int)
        for img_path in group_images:
            if img_path in image_objects:
                for obj in image_objects[img_path]:
                    group_objects[obj['label']] += 1
        for obj_label, count in group_objects.items():
            print(f"  - {obj_label}: found in {count} images")
            
        for img_path in group_images:
            dst = group_dir / img_path.name
            shutil.copy2(img_path, dst)
            print(f"  Copied {img_path.name}")
    
    # Report isolated images
    isolated = [img for img, label in zip(image_files, clustering.labels_) 
                if label == -1]
    if isolated:
        print(f"\nFound {len(isolated)} images with no matching objects:")
        for img in isolated:
            if img in image_objects:
                print(f"  {img.name} (detected objects: {[obj['label'] for obj in image_objects[img]]})")
            else:
                print(f"  {img.name} (no objects detected)")
    
    print(f"\nImages grouped into {len(groups)} categories")
    print(f"Results saved in: {output_path}")
    
    return groups

if __name__ == "__main__":
    dataset_path = Path("dataset")
    input_path = dataset_path / "images"
    output_path = dataset_path / "grouped_images_gdino"
    
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