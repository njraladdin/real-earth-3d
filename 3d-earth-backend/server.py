from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import uuid
import time
from werkzeug.utils import secure_filename
import logging
from PIL import Image
import io
import threading
from run_colmap import run_colmap_pipeline
from run_opensplat import run_opensplat_pipeline
import tempfile
import shutil

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
MAX_IMAGE_SIZE = (1200, 1200)  # Maximum dimensions for uploaded images
BASE_URL = 'http://localhost:5000'  # Base URL for image links

# Create upload directory if it doesn't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max upload size
app.config['BASE_URL'] = BASE_URL

# Add a dictionary to track processing status
splat_jobs = {}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def compress_image(image_data):
    """Compress image to reduce file size"""
    try:
        img = Image.open(io.BytesIO(image_data))
        
        # Convert to RGB if image has alpha channel
        if img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info):
            background = Image.new('RGB', img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[3] if img.mode == 'RGBA' else None)
            img = background
        
        # Resize if larger than MAX_IMAGE_SIZE
        if img.width > MAX_IMAGE_SIZE[0] or img.height > MAX_IMAGE_SIZE[1]:
            img.thumbnail(MAX_IMAGE_SIZE, Image.LANCZOS)
        
        output = io.BytesIO()
        img.save(output, format='JPEG', quality=85, optimize=True)
        return output.getvalue()
    except Exception as e:
        logger.error(f"Error compressing image: {e}")
        return image_data  # Return original if compression fails

@app.route('/api/upload', methods=['POST'])
def upload_file():
    """Upload one or more images for a specific chunk and spot"""
    if 'files' not in request.files:
        return jsonify({'error': 'No files part in the request'}), 400
    
    files = request.files.getlist('files')
    chunk_id = request.form.get('chunk_id')
    spot_id = request.form.get('spot_id', str(uuid.uuid4()))
    
    if not chunk_id:
        return jsonify({'error': 'Chunk ID is required'}), 400
    
    # Create directory structure if it doesn't exist
    chunk_dir = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(chunk_id))
    spot_dir = os.path.join(chunk_dir, secure_filename(spot_id))
    os.makedirs(spot_dir, exist_ok=True)
    
    uploaded_files = []
    
    for file in files:
        if file and allowed_file(file.filename):
            # Generate a unique filename
            original_filename = secure_filename(file.filename)
            filename = f"{int(time.time())}_{original_filename}"
            filepath = os.path.join(spot_dir, filename)
            
            # Compress and save the image
            file_data = file.read()
            compressed_data = compress_image(file_data)
            
            with open(filepath, 'wb') as f:
                f.write(compressed_data)
            
            # Generate URL for the uploaded file - include full URL with host
            file_url = f"{app.config['BASE_URL']}/api/images/{chunk_id}/{spot_id}/{filename}"
            
            uploaded_files.append({
                'url': file_url,
                'fileName': filename,
                'originalName': original_filename
            })
        else:
            return jsonify({'error': f'Invalid file type for {file.filename}'}), 400
    
    return jsonify({
        'success': True,
        'files': uploaded_files,
        'chunk_id': chunk_id,
        'spot_id': spot_id
    })

@app.route('/api/images/<chunk_id>/<spot_id>/<filename>', methods=['GET'])
def get_image(chunk_id, spot_id, filename):
    """Retrieve a specific image"""
    directory = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(chunk_id), secure_filename(spot_id))
    return send_from_directory(directory, filename)

@app.route('/api/images/<chunk_id>/<spot_id>', methods=['GET'])
def list_spot_images(chunk_id, spot_id):
    """List all images for a specific spot"""
    directory = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(chunk_id), secure_filename(spot_id))
    
    try:
        if not os.path.exists(directory):
            return jsonify({'images': []})
        
        files = os.listdir(directory)
        images = []
        
        for filename in files:
            if allowed_file(filename):
                file_url = f"{app.config['BASE_URL']}/api/images/{chunk_id}/{spot_id}/{filename}"
                images.append({
                    'url': file_url,
                    'fileName': filename
                })
        
        return jsonify({'images': images})
    except Exception as e:
        logger.error(f"Error listing images: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/images/<chunk_id>', methods=['GET'])
def list_chunk_images(chunk_id):
    """List all spots and their images for a specific chunk"""
    chunk_dir = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(chunk_id))
    
    try:
        if not os.path.exists(chunk_dir):
            return jsonify({'spots': []})
        
        spots = []
        spot_dirs = os.listdir(chunk_dir)
        
        for spot_id in spot_dirs:
            spot_path = os.path.join(chunk_dir, spot_id)
            if os.path.isdir(spot_path):
                images = []
                for filename in os.listdir(spot_path):
                    if allowed_file(filename):
                        file_url = f"{app.config['BASE_URL']}/api/images/{chunk_id}/{spot_id}/{filename}"
                        images.append({
                            'url': file_url,
                            'fileName': filename
                        })
                
                spots.append({
                    'spot_id': spot_id,
                    'images': images
                })
        
        return jsonify({'spots': spots})
    except Exception as e:
        logger.error(f"Error listing chunk images: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/delete/<chunk_id>/<spot_id>/<filename>', methods=['DELETE'])
def delete_image(chunk_id, spot_id, filename):
    """Delete a specific image"""
    filepath = os.path.join(
        app.config['UPLOAD_FOLDER'], 
        secure_filename(chunk_id), 
        secure_filename(spot_id), 
        secure_filename(filename)
    )
    
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'File not found'}), 404
    except Exception as e:
        logger.error(f"Error deleting image: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/delete/spot/<chunk_id>/<spot_id>', methods=['DELETE'])
def delete_spot(chunk_id, spot_id):
    """Delete an entire spot and all its images"""
    spot_dir = os.path.join(
        app.config['UPLOAD_FOLDER'], 
        secure_filename(chunk_id), 
        secure_filename(spot_id)
    )
    
    try:
        if os.path.exists(spot_dir):
            # Delete all files in the directory
            for filename in os.listdir(spot_dir):
                file_path = os.path.join(spot_dir, filename)
                if os.path.isfile(file_path):
                    os.remove(file_path)
            
            # Remove the directory
            os.rmdir(spot_dir)
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Spot not found'}), 404
    except Exception as e:
        logger.error(f"Error deleting spot: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Simple health check endpoint"""
    return jsonify({'status': 'healthy'})

@app.route('/api/create-splat', methods=['POST'])
def create_splat():
    """Create a 3D splat from selected spots"""
    try:
        data = request.json
        
        if not data or 'chunk_id' not in data or 'spots' not in data:
            return jsonify({'error': 'Missing required data (chunk_id or spots)'}), 400
        
        chunk_id = data['chunk_id']
        spot_ids = data['spots']
        
        if not spot_ids:
            return jsonify({'error': 'No spots selected'}), 400
        
        logger.info(f"Creating splat for chunk {chunk_id} with spots: {spot_ids}")
        
        # Generate a unique job ID
        job_id = str(uuid.uuid4())
        
        # Create a temporary directory for processing
        temp_dir = tempfile.mkdtemp(prefix=f"splat_job_{job_id}_")
        images_dir = os.path.join(temp_dir, "images")
        os.makedirs(images_dir, exist_ok=True)
        
        # Collect all images from the selected spots
        all_images = []
        for spot_id in spot_ids:
            spot_dir = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(chunk_id), secure_filename(spot_id))
            
            if os.path.exists(spot_dir):
                for filename in os.listdir(spot_dir):
                    if allowed_file(filename):
                        image_path = os.path.join(spot_dir, filename)
                        # Copy image to the temporary directory
                        shutil.copy2(image_path, os.path.join(images_dir, filename))
                        all_images.append({
                            'path': image_path,
                            'spot_id': spot_id,
                            'filename': filename,
                            'url': f"{app.config['BASE_URL']}/api/images/{chunk_id}/{spot_id}/{filename}"
                        })
        
        # Log the images that will be processed
        logger.info(f"Found {len(all_images)} images for splat creation")
        
        # Initialize job status
        splat_jobs[job_id] = {
            'status': 'processing',
            'chunk_id': chunk_id,
            'spot_ids': spot_ids,
            'image_count': len(all_images),
            'temp_dir': temp_dir,
            'start_time': time.time(),
            'progress': 0,
            'message': 'Starting processing...'
        }
        
        # Start processing in a background thread
        thread = threading.Thread(
            target=process_splat_job,
            args=(job_id, temp_dir, chunk_id)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'message': 'Splat creation started',
            'job_id': job_id,
            'chunk_id': chunk_id,
            'spot_ids': spot_ids,
            'image_count': len(all_images),
            'status': 'processing'
        })
        
    except Exception as e:
        logger.error(f"Error creating splat: {e}")
        return jsonify({'error': str(e)}), 500

def process_splat_job(job_id, temp_dir, chunk_id):
    """Process a splat job in the background"""
    try:
        # Update job status
        splat_jobs[job_id]['message'] = 'Running COLMAP...'
        splat_jobs[job_id]['progress'] = 10
        
        # Run COLMAP
        dataset_path = os.path.join(temp_dir, "dataset")
        images_path = os.path.join(temp_dir, "images")
        
        try:
            # Run COLMAP pipeline
            colmap_stats = run_colmap_pipeline(
                dataset_path=dataset_path,
                input_images_path=images_path,
                cleanup_existing=True
            )
            
            # Check if enough images were registered
            total_images = colmap_stats.get('total_images', 0)
            registered_images = colmap_stats.get('registered_images', 0)
            
            if total_images > 0:
                registration_percentage = (registered_images / total_images) * 100
                splat_jobs[job_id]['registration_percentage'] = registration_percentage
                splat_jobs[job_id]['registered_images'] = registered_images
                splat_jobs[job_id]['total_images'] = total_images
                
                logger.info(f"COLMAP registered {registered_images}/{total_images} images ({registration_percentage:.1f}%)")
                
                # If less than 50% of images were registered, fail the job
                if registration_percentage < 50:
                    splat_jobs[job_id]['status'] = 'failed'
                    splat_jobs[job_id]['message'] = f'Insufficient image registration: only {registration_percentage:.1f}% of images were registered (minimum 50% required)'
                    splat_jobs[job_id]['error_details'] = 'Not enough images could be registered. Try adding more images with better overlap.'
                    logger.warning(f"Job {job_id} failed due to insufficient image registration: {registration_percentage:.1f}%")
                    return
            else:
                # No images were processed
                splat_jobs[job_id]['status'] = 'failed'
                splat_jobs[job_id]['message'] = 'No images were registered by COLMAP'
                splat_jobs[job_id]['error_details'] = 'COLMAP could not register any images. The images may not have enough visual overlap.'
                logger.warning(f"Job {job_id} failed: no images were registered by COLMAP")
                return
                
        except RuntimeError as e:
            # Handle specific COLMAP errors
            error_message = str(e)
            splat_jobs[job_id]['status'] = 'failed'
            splat_jobs[job_id]['message'] = f'COLMAP processing failed: {error_message}'
            splat_jobs[job_id]['error_details'] = error_message
            logger.error(f"COLMAP error in job {job_id}: {error_message}")
            return
        
        # Update job status
        splat_jobs[job_id]['message'] = 'Running OpenSplat...'
        splat_jobs[job_id]['progress'] = 50
        
        # Run OpenSplat
        try:
            run_opensplat_pipeline(
                dataset_path=dataset_path,
                num_points=2000  # Adjust as needed
            )
        except Exception as e:
            # Handle OpenSplat errors
            error_message = f"OpenSplat processing failed: {str(e)}"
            splat_jobs[job_id]['status'] = 'failed'
            splat_jobs[job_id]['message'] = error_message
            splat_jobs[job_id]['error_details'] = str(e)
            logger.error(f"OpenSplat error in job {job_id}: {str(e)}")
            return
        
        # Copy the resulting splat file to a permanent location
        splat_output = os.path.join(dataset_path, "splat.ply")
        
        # Create directory for splats if it doesn't exist
        splats_dir = os.path.join(app.config['UPLOAD_FOLDER'], "splats")
        os.makedirs(splats_dir, exist_ok=True)
        
        # Create a unique filename for the splat
        splat_filename = f"splat_{chunk_id}_{int(time.time())}.ply"
        splat_destination = os.path.join(splats_dir, splat_filename)
        
        # Copy the splat file
        if os.path.exists(splat_output):
            shutil.copy2(splat_output, splat_destination)
            
            # Update job status
            splat_jobs[job_id]['status'] = 'completed'
            splat_jobs[job_id]['progress'] = 100
            splat_jobs[job_id]['message'] = 'Splat creation completed'
            splat_jobs[job_id]['splat_url'] = f"{app.config['BASE_URL']}/api/splats/{splat_filename}"
            splat_jobs[job_id]['splat_filename'] = splat_filename
            splat_jobs[job_id]['completion_time'] = time.time()
        else:
            # Update job status for failure
            splat_jobs[job_id]['status'] = 'failed'
            splat_jobs[job_id]['message'] = 'Failed to generate splat file'
            splat_jobs[job_id]['error_details'] = 'The splat file was not created. This may be due to an issue with the 3D reconstruction.'
            
    except Exception as e:
        logger.error(f"Error in splat job {job_id}: {e}")
        # Update job status for error
        splat_jobs[job_id]['status'] = 'failed'
        splat_jobs[job_id]['message'] = f'Error: {str(e)}'
        splat_jobs[job_id]['error_details'] = str(e)
    finally:
        # Clean up temporary directory after a delay (to allow file access to complete)
        def cleanup_temp_dir():
            try:
                time.sleep(60)  # Wait a minute before cleanup
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
                    logger.info(f"Cleaned up temporary directory: {temp_dir}")
            except Exception as e:
                logger.error(f"Error cleaning up temp dir: {e}")
                
        cleanup_thread = threading.Thread(target=cleanup_temp_dir)
        cleanup_thread.daemon = True
        cleanup_thread.start()

@app.route('/api/splat-status/<job_id>', methods=['GET'])
def get_splat_status(job_id):
    """Get the status of a splat creation job"""
    if job_id not in splat_jobs:
        return jsonify({'error': 'Job not found'}), 404
        
    job = splat_jobs[job_id]
    
    # Calculate elapsed time
    elapsed = time.time() - job['start_time']
    
    response = {
        'job_id': job_id,
        'status': job['status'],
        'progress': job['progress'],
        'message': job['message'],
        'elapsed_seconds': int(elapsed),
        'chunk_id': job['chunk_id'],
        'image_count': job['image_count']
    }
    
    # Add registration stats if available
    if 'registration_percentage' in job:
        response['registration_percentage'] = job['registration_percentage']
        response['registered_images'] = job['registered_images']
        response['total_images'] = job['total_images']
    
    # Add splat URL if completed
    if job['status'] == 'completed' and 'splat_url' in job:
        response['splat_url'] = job['splat_url']
        response['splat_filename'] = job['splat_filename']
    
    # Add error details if failed
    if job['status'] == 'failed' and 'error_details' in job:
        response['error_details'] = job['error_details']
        
    return jsonify(response)

@app.route('/api/splats/<filename>', methods=['GET'])
def get_splat(filename):
    """Serve a splat file"""
    splats_dir = os.path.join(app.config['UPLOAD_FOLDER'], "splats")
    return send_from_directory(splats_dir, filename)

@app.route('/api/splats', methods=['GET'])
def list_splats():
    """List all available splat files"""
    splats_dir = os.path.join(app.config['UPLOAD_FOLDER'], "splats")
    os.makedirs(splats_dir, exist_ok=True)
    
    splats = []
    for filename in os.listdir(splats_dir):
        if filename.endswith('.ply'):
            splat_url = f"{app.config['BASE_URL']}/api/splats/{filename}"
            # Try to extract chunk_id from filename
            chunk_id = None
            parts = filename.split('_')
            if len(parts) > 1 and parts[0] == 'splat':
                chunk_id = parts[1]
                
            splats.append({
                'filename': filename,
                'url': splat_url,
                'chunk_id': chunk_id,
                'created': os.path.getctime(os.path.join(splats_dir, filename))
            })
    
    # Sort by creation time (newest first)
    splats.sort(key=lambda x: x['created'], reverse=True)
    
    return jsonify({'splats': splats})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
