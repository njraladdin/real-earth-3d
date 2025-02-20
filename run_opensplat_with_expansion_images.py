from run_opensplat import run_opensplat_pipeline

def main():
    try:
        # Run OpenSplat with dataset_main path
        run_opensplat_pipeline(
            dataset_path="dataset_staging"
        )
    except Exception as e:
        print(f"Error: {e}")
        exit(1)

if __name__ == "__main__":
    main() 