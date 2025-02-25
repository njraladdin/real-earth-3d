import os
import subprocess
from pathlib import Path
import shutil
from datetime import datetime
import platform
import sys

def run_command(command, cwd=None, shell=False):
    """Run a command and check for errors"""
    try:
        process = subprocess.run(
            command, 
            check=True, 
            cwd=cwd, 
            shell=shell,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        return process.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {' '.join(command) if isinstance(command, list) else command}")
        print(f"Error output: {e.stderr}")
        raise e

def is_windows():
    """Check if running on Windows"""
    return platform.system() == "Windows"

def setup_visual_studio_env():
    """Setup Visual Studio environment variables on Windows"""
    if not is_windows():
        return  # Not needed on non-Windows platforms
        
    vs_paths = [
        r"C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat",
        r"C:\Program Files\Microsoft Visual Studio\2022\Professional\VC\Auxiliary\Build\vcvars64.bat",
        r"C:\Program Files\Microsoft Visual Studio\2022\Enterprise\VC\Auxiliary\Build\vcvars64.bat",
        r"C:\Program Files (x86)\Microsoft Visual Studio\2019\Community\VC\Auxiliary\Build\vcvars64.bat",
        r"C:\Program Files (x86)\Microsoft Visual Studio\2019\Professional\VC\Auxiliary\Build\vcvars64.bat",
        r"C:\Program Files (x86)\Microsoft Visual Studio\2019\Enterprise\VC\Auxiliary\Build\vcvars64.bat",
    ]
    
    for vs_path in vs_paths:
        if os.path.exists(vs_path):
            print(f"Found Visual Studio at: {vs_path}")
            # Call vcvars64.bat and get the environment
            run_command(vs_path, shell=True)
            return
    
    print("Warning: Visual Studio not found. Build may fail if environment is not properly set up.")

def find_dependencies():
    """Find dependencies based on platform"""
    deps = {}
    
    if is_windows():
        # Windows dependency paths
        libtorch_paths = [
            r"C:\libtorch",
            r"C:\Program Files\libtorch",
            r"C:\Users\Mega-PC\Desktop\projects\map_to_3d\libtorch",
        ]
        
        opencv_paths = [
            r"C:\opencv\build",
            r"C:\Program Files\opencv\build",
            r"C:\Users\Mega-PC\Desktop\projects\map_to_3d\opencv\build",
        ]
        
        cuda_paths = [
            r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.5",
            r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.4",
            r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.3",
            r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.2",
            r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.1",
            r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v12.0",
            r"C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v11.8",
        ]
        
        # Find libtorch
        for path in libtorch_paths:
            if os.path.exists(path):
                deps['libtorch_path'] = path
                break
                
        # Find OpenCV
        for path in opencv_paths:
            if os.path.exists(path):
                deps['opencv_path'] = path
                break
                
        # Find CUDA
        for path in cuda_paths:
            if os.path.exists(path):
                deps['cuda_path'] = path
                break
    else:
        # Linux/macOS - assume dependencies are in standard locations
        deps['libtorch_path'] = "/usr/local/libtorch"
        deps['opencv_path'] = "/usr/local"
        deps['cuda_path'] = "/usr/local/cuda"
    
    # Print found dependencies
    print("Found dependencies:")
    for key, value in deps.items():
        if key in deps:
            print(f"  {key}: {value}")
        else:
            print(f"  {key}: Not found")
            
    return deps

def run_opensplat_pipeline(
    dataset_path="dataset",
    num_points=1500,
    libtorch_path=None,
    opencv_path=None,
    cuda_path=None
):
    """
    Run the OpenSplat pipeline
    
    Args:
        dataset_path (str): Path to the dataset (relative to script directory or absolute)
        num_points (int): Number of points to process
        libtorch_path (str, optional): Path to libtorch installation
        opencv_path (str, optional): Path to OpenCV build directory
        cuda_path (str, optional): Path to CUDA installation
    """
    # Get the script's directory for consistent paths
    script_dir = Path(__file__).parent.absolute()
    
    # Convert dataset_path to absolute path if it's relative
    if not os.path.isabs(dataset_path):
        dataset_path = str(script_dir / dataset_path)
    
    # Find dependencies if not provided
    deps = find_dependencies()
    libtorch_path = libtorch_path or deps.get('libtorch_path')
    opencv_path = opencv_path or deps.get('opencv_path')
    cuda_path = cuda_path or deps.get('cuda_path')
    
    # Setup Visual Studio environment on Windows
    if is_windows():
        setup_visual_studio_env()

    # Clone OpenSplat if not exists
    opensplat_dir = script_dir / "OpenSplat"
    if not opensplat_dir.exists():
        print("Cloning OpenSplat repository...")
        run_command(["git", "clone", "https://github.com/pierotofy/OpenSplat", str(opensplat_dir)])

    # Check if OpenSplat is already built
    build_dir = opensplat_dir / "build"
    
    if is_windows():
        release_dir = build_dir / "Release"
        opensplat_exe = release_dir / "opensplat.exe"
    else:
        opensplat_exe = build_dir / "opensplat"

    if not opensplat_exe.exists():
        print("OpenSplat executable not found. Building...")
        # Create and enter build directory
        build_dir.mkdir(exist_ok=True)

        # Configure CMake
        print("Configuring CMake...")
        cmake_command = ["cmake"]
        
        if libtorch_path:
            cmake_command.append(f"-DCMAKE_PREFIX_PATH={libtorch_path}")
        
        if opencv_path:
            cmake_command.append(f"-DOPENCV_DIR={opencv_path}")
            
        cmake_command.append("-DCMAKE_BUILD_TYPE=Release")
        
        if is_windows() and cuda_path:
            cmake_command.append(f'-DCMAKE_GENERATOR_TOOLSET=cuda={cuda_path}')
            
        cmake_command.append("..")
        
        run_command(cmake_command, cwd=str(build_dir))

        # Build the project
        print("Building OpenSplat...")
        run_command(["cmake", "--build", ".", "--config", "Release"], cwd=str(build_dir))
    else:
        print("OpenSplat already built, skipping build steps...")

    # Run OpenSplat
    print("Running OpenSplat...")
    # Determine the working directory and executable path
    if is_windows():
        working_dir = str(release_dir)
        exe_path = str(opensplat_exe)
    else:
        working_dir = str(build_dir)
        exe_path = str(opensplat_exe)
        
    run_command([
        exe_path,
        dataset_path,
        "-n", str(num_points)
    ], cwd=working_dir)

    # Copy the output splat file to dataset
    if is_windows():
        splat_file = release_dir / "splat.ply"
    else:
        splat_file = build_dir / "splat.ply"
        
    if splat_file.exists():
        # Copy to dataset folder
        dataset_splat_file = Path(dataset_path) / "splat.ply"
        shutil.copy2(splat_file, dataset_splat_file)
        print(f"Copied splat file to dataset: {dataset_splat_file}")
        return str(dataset_splat_file)
    else:
        print(f"Warning: Splat file not found at {splat_file}")
        return None

if __name__ == "__main__":
    try:
        run_opensplat_pipeline()
    except Exception as e:
        print(f"Error: {e}")
        exit(1) 