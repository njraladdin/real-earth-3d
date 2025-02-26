import os
import subprocess
from pathlib import Path
import shutil
from datetime import datetime

def run_command(command, cwd=None, shell=False):
    """Run a command and check for errors"""
    try:
        subprocess.run(command, check=True, cwd=cwd, shell=shell)
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {' '.join(command) if isinstance(command, list) else command}")
        raise e

def setup_visual_studio_env():
    """Setup Visual Studio environment variables"""
    vs_path = r"C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat"
    if not os.path.exists(vs_path):
        raise FileNotFoundError(f"Visual Studio path not found: {vs_path}")
    
    # Call vcvars64.bat and get the environment
    run_command(vs_path, shell=True)

def run_opensplat_pipeline(
    libtorch_path=r"C:\Users\Mega-PC\Desktop\projects\map_to_3d\libtorch",
    opencv_path=r"C:\Users\Mega-PC\Desktop\projects\map_to_3d\opencv\build",
    cuda_path=r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.5",
    dataset_path="dataset_merged",
    num_points=1500
):
    """
    Run the OpenSplat pipeline
    
    Args:
        libtorch_path (str): Path to libtorch installation
        opencv_path (str): Path to OpenCV build directory
        cuda_path (str): Path to CUDA installation
        dataset_path (str): Path to the dataset (relative to script directory or absolute)
        num_points (int): Number of points to process
    """
    # Setup Visual Studio environment
    print("Setting up Visual Studio environment...")
    setup_visual_studio_env()

    # Get the script's directory for consistent paths
    script_dir = Path(__file__).parent.absolute()
    
    # Convert dataset_path to absolute path if it's relative
    dataset_path = str(script_dir / dataset_path)
    
    # Clone OpenSplat if not exists
    opensplat_dir = script_dir / "OpenSplat"
    if not opensplat_dir.exists():
        print("Cloning OpenSplat repository...")
        run_command(["git", "clone", "https://github.com/pierotofy/OpenSplat", str(opensplat_dir)])

    # Check if OpenSplat is already built
    build_dir = opensplat_dir / "build"
    release_dir = build_dir / "Release"
    opensplat_exe = release_dir / "opensplat.exe"

    if not opensplat_exe.exists():
        print("OpenSplat executable not found. Building...")
        # Create and enter build directory
        build_dir.mkdir(exist_ok=True)

        # Configure CMake
        print("Configuring CMake...")
        cmake_command = [
            "cmake",
            "-DCMAKE_PREFIX_PATH=" + libtorch_path,
            f"-DOPENCV_DIR={opencv_path}",
            "-DCMAKE_BUILD_TYPE=Release",
            f'-DCMAKE_GENERATOR_TOOLSET=cuda={cuda_path}',
            ".."
        ]
        run_command(cmake_command, cwd=str(build_dir))

        # Build the project
        print("Building OpenSplat...")
        run_command(["cmake", "--build", ".", "--config", "Release"], cwd=str(build_dir))
    else:
        print("OpenSplat already built, skipping build steps...")

    # Run OpenSplat
    print("Running OpenSplat...")
    # Change working directory to OpenSplat build/Release for consistent output location
    run_command([
        str(opensplat_exe),
        dataset_path,
        "-n", str(num_points)
    ], cwd=str(release_dir))  # Added cwd parameter to ensure splat.ply is created in Release directory

    # Copy the output splat file with timestamp and to dataset
    splat_file = release_dir / "splat.ply"
    if splat_file.exists():
        # Create recent_splats directory if it doesn't exist
        recent_splats_dir = script_dir / "recent_splats"
        recent_splats_dir.mkdir(exist_ok=True)
        
        # Generate timestamp and new filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        new_splat_file = recent_splats_dir / f"splat_{timestamp}.ply"
        
        # Copy the file to recent_splats with timestamp
        shutil.copy2(splat_file, new_splat_file)
        print(f"Copied splat file to: {new_splat_file}")

        # Also copy to dataset folder
        dataset_splat_file = Path(dataset_path) / "splat.ply"
        shutil.copy2(splat_file, dataset_splat_file)
        print(f"Copied splat file to dataset: {dataset_splat_file}")

if __name__ == "__main__":
    try:
        run_opensplat_pipeline()
    except Exception as e:
        print(f"Error: {e}")
        exit(1) 