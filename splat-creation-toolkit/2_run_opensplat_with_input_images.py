from run_opensplat import run_opensplat_pipeline

def main():
    try:
        # Run OpenSplat with dataset_main path
        # dataset_path = "hloc_output/sfm"
        dataset_path = "colmap_output"
        run_opensplat_pipeline(
            dataset_path=dataset_path,
            num_points=1100
        )
        print("Successfully ran OpenSplat pipeline")
        
    except Exception as e:
        print(f"Error: {e}")
        exit(1)

if __name__ == "__main__":
    main() 