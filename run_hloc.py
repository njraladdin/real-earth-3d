import torch
from pathlib import Path
import logging
from hloc import extract_features, match_features, reconstruction, pairs_from_exhaustive

def setup_logging():
    """Configure logging to show detailed progress"""
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] %(levelname)s: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    return logging.getLogger('hloc')

def run_hloc_pipeline(input_dir='initial_images', output_dir='hloc_output'):
    """
    Run the HLOC pipeline using SuperPoint + SuperGlue with GPU acceleration
    
    Args:
        input_dir: Directory containing input images
        output_dir: Directory for outputs
    """
    logger = setup_logging()
    
    # Check GPU availability
    if torch.cuda.is_available():
        device = torch.device('cuda')
        logger.info(f"Using GPU: {torch.cuda.get_device_name(0)}")
        torch.cuda.empty_cache()  # Clear GPU memory
    else:
        device = torch.device('cpu')
        logger.warning("No GPU available, using CPU")
    
    # Convert paths to Path objects
    images = Path(input_dir)
    outputs = Path(output_dir)
    
    # Check input directory
    if not images.exists():
        raise FileNotFoundError(f"Input directory {images} does not exist!")
    
    # Clean up existing output directory to avoid permission issues
    if outputs.exists():
        logger.info(f"Cleaning up existing output directory: {outputs}")
        import shutil
        shutil.rmtree(outputs)
    
    # Create fresh output directory
    outputs.mkdir(parents=True, exist_ok=True)
    
    try:
        # Define paths for intermediate files
        sfm_pairs = outputs / 'pairs-sfm.txt'
        sfm_dir = outputs / 'sfm'
        features = outputs / 'features.h5'
        matches = outputs / 'matches.h5'
        sfm_images_dir = sfm_dir / 'images'  # New path for copied images

        # Create sfm/images directory
        sfm_images_dir.mkdir(parents=True, exist_ok=True)

        # Get list of images and copy them to sfm/images
        references = []
        for p in images.iterdir():
            if p.is_file() and p.suffix.lower() in {'.jpg', '.jpeg', '.png', '.tif', '.tiff'}:
                references.append(str(p.relative_to(images)))
                # Copy image to sfm/images directory
                import shutil
                shutil.copy2(p, sfm_images_dir / p.name)
        
        if not references:
            logger.error("No valid images found in input directory!")
            return
            
        logger.info(f"Found and copied {len(references)} images to {sfm_images_dir}")

        # Get feature and matcher configurations optimized for GPU
        feature_conf = extract_features.confs['superpoint_aachen'].copy()  # GPU-optimized SuperPoint
        matcher_conf = match_features.confs['superglue'].copy()  # Using SuperGlue matcher
        
        # Print detailed configurations
        logger.info("\nSuperPoint Configuration:")
        for key, value in feature_conf.items():
            logger.info(f"{key}: {value}")
            
        logger.info("\nSuperGlue Configuration:")
        for key, value in matcher_conf['model'].items():
            logger.info(f"{key}: {value}")

        # Adjust SuperGlue parameters for more thorough matching
        matcher_conf['model'].update({
            'sinkhorn_iterations': 100,  # Increased from default 20
            'match_threshold': 0.2,  # Lower threshold allows more matches
            'num_layers': 9  # Default is 9, can increase for more thorough (but slower) matching
        })
        
        # Extract features with GPU acceleration
        logger.info("Extracting features with SuperPoint...")
        extract_features.main(feature_conf, images, image_list=references, feature_path=features, as_half=True)

        # Generate pairs and match features with GPU acceleration
        logger.info("Generating pairs and matching features with SuperGlue...")
        pairs_from_exhaustive.main(sfm_pairs, image_list=references)
        match_features.main(matcher_conf, sfm_pairs, features=features, matches=matches)

        # Run reconstruction
        logger.info("Running reconstruction...")
        model = reconstruction.main(sfm_dir, images, sfm_pairs, features, matches, image_list=references)

        # Print statistics
        if model and model.cameras:
            n_images = len(model.cameras)
            n_points = len(model.points3D)
            logger.info(f"\nReconstruction Statistics:")
            logger.info(f"Reconstructed images: {n_images}")
            logger.info(f"3D points: {n_points}")
            logger.info(f"Output directory: {outputs}")
            logger.info("✨ Pipeline completed successfully!")
        else:
            logger.warning("No reconstruction was created. The process might have failed.")
            
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == '__main__':
    import sys
    
    # Parse command line arguments
    input_dir = 'initial_images_filtered'
    output_dir = 'hloc_output'
    if len(sys.argv) > 1:
        input_dir = sys.argv[1]
    if len(sys.argv) > 2:
        output_dir = sys.argv[2]
    
    run_hloc_pipeline(input_dir, output_dir) 