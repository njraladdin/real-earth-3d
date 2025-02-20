import torch
from PIL import Image
import numpy as np
from pathlib import Path
import shutil
import clip
from sklearn.preprocessing import StandardScaler
from sklearn.metrics.pairwise import cosine_similarity

class ImageMatcher:
    def __init__(self, source_path, groups_path):
        """
        Initialize the matcher with source and groups paths
        
        Args:
            source_path (str|Path): Path to directory containing source images
            groups_path (str|Path): Path to directory containing grouped images
        """
        self.source_path = Path(source_path)
        self.groups_path = Path(groups_path)
        
        # Setup CLIP
        print("Loading CLIP model...")
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model, self.preprocess = clip.load("ViT-L/14", self.device)

    def extract_features(self, image_paths):
        features = {}
        batch_size = 8
        
        for i in range(0, len(image_paths), batch_size):
            batch_files = image_paths[i:i + batch_size]
            try:
                images = [Image.open(img_path).convert('RGB') for img_path in batch_files]
                image_inputs = torch.stack([self.preprocess(img) for img in images]).to(self.device)
                
                with torch.no_grad():
                    batch_features = self.model.encode_image(image_inputs)
                    batch_features = batch_features.cpu().numpy()
                    
                    for idx, img_path in enumerate(batch_files):
                        features[str(img_path)] = batch_features[idx]
                        
            except Exception as e:
                print(f"Error processing batch: {e}")
                continue
                
        return features

    def match_images_with_group(self, output_path):
        """
        Match source images with existing image groups and copy matching group + source images
        to output directory
        
        Args:
            output_path (str|Path): Path where matched images will be copied
        """
        output_path = Path(output_path)
        
        if not self.source_path.exists() or not self.groups_path.exists():
            print("Error: Input directories not found")
            return None
            
        # Clear output directory
        if output_path.exists():
            shutil.rmtree(output_path)
        output_path.mkdir(parents=True)
        
        # Get source images
        source_image_files = list(self.source_path.glob('*.[jJ][pP][gG]')) + \
                         list(self.source_path.glob('*.[pP][nN][gG]'))
        
        if not source_image_files:
            print("No source images found!")
            return None
        
        # Extract features for source images
        print("Processing source images...")
        source_image_features = self.extract_features(source_image_files)
        
        # Get existing groups and their features
        groups = {}
        group_features = {}
        
        for group_dir in self.groups_path.glob('group_*'):
            group_images = list(group_dir.glob('*.[jJ][pP][gG]')) + \
                          list(group_dir.glob('*.[pP][nN][gG]'))
            if group_images:
                group_id = group_dir.name
                groups[group_id] = group_images
                group_features[group_id] = self.extract_features(group_images)
        
        if not groups:
            print("No existing groups found!")
            return None
        
        # Calculate average similarity between source images and each group
        print("\nFinding best matching group...")
        group_similarities = {}
        
        for group_id, group_feat in group_features.items():
            # Convert features to arrays
            group_vectors = np.array(list(group_feat.values()))
            new_vectors = np.array(list(source_image_features.values()))
            
            # Calculate average similarity
            sim_matrix = cosine_similarity(new_vectors, group_vectors)
            avg_similarity = np.mean(sim_matrix)
            group_similarities[group_id] = avg_similarity
            
            print(f"Average similarity with {group_id}: {avg_similarity:.3f}")
        
        # Find best matching group
        if not group_similarities:
            return None
            
        best_group = max(group_similarities.items(), key=lambda x: x[1])
        
        # Check if similarity is too low
        if best_group[1] < 0.2:  # You can adjust this threshold
            print("\nNo sufficiently similar group found")
            return None
        
        print(f"\nBest matching group: {best_group[0]} (similarity: {best_group[1]:.3f})")
        
        # Copy best matching group and source images to output
        print("\nCopying images to output directory...")
        
        # Copy source images
        for img_path in source_image_files:
            dst = output_path / img_path.name
            shutil.copy2(str(img_path), str(dst))
            print(f"Copied source image: {img_path.name}")
        
        # Copy matching group
        for img_path in groups[best_group[0]]:
            dst = output_path / img_path.name
            shutil.copy2(str(img_path), str(dst))
            print(f"Copied group image: {img_path.name}")
        
        print(f"\nResults saved in: {output_path}")
        return best_group[0]

if __name__ == "__main__":
    dataset_path = Path("dataset_main")
    source_images_path = Path("expansion_images_filtered")
    grouped_images_path = dataset_path / "grouped_images"
    output_path = Path("expansion_images_with_group")
    
    try:
        matcher = ImageMatcher(source_images_path, grouped_images_path)
        matching_group = matcher.match_images_with_group(output_path)
        if matching_group:
            print(f"\nSuccessfully matched with {matching_group}")
        else:
            print("\nNo matching group found")
    except Exception as e:
        import traceback
        print(f"Error: {e}")
        print(traceback.format_exc())
        exit(1) 