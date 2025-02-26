from run_colmap import run_colmap_pipeline

def main():
    try:
        run_colmap_pipeline(
            dataset_path="colmap_output",
            input_images_path="input_images",
            cleanup_existing=True  # Don't clear existing files for initial run
        )
    except Exception as e:
        print(f"Error: {e}")
        exit(1)

if __name__ == "__main__":
    main()  