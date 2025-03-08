import React, { useState, useRef, useEffect } from 'react';
import { ref, uploadBytesResumable, getDownloadURL, deleteObject } from 'firebase/storage';
import { doc, setDoc, getDocs, deleteDoc, updateDoc, collection } from 'firebase/firestore';
import { storage, db } from '../firebaseConfig';
import { UploadModal } from './UploadModal';

// Helper function to download files from URLs
const downloadFile = async (url, filename) => {
  try {
    // Fetch the file content
    const response = await fetch(url);
    
    if (!response.ok) {
      throw new Error(`Failed to download file: ${response.statusText}`);
    }
    
    // Convert to blob
    const blob = await response.blob();
    
    // Create an object URL for the blob
    const objectUrl = URL.createObjectURL(blob);
    
    // Create a temporary anchor element
    const a = document.createElement('a');
    a.href = objectUrl;
    a.download = filename || 'splat-file.splat'; // Default filename if none provided
    document.body.appendChild(a);
    
    // Trigger the download
    a.click();
    
    // Clean up
    URL.revokeObjectURL(objectUrl);
    document.body.removeChild(a);
    
    return true;
  } catch (error) {
    console.error("Error downloading file:", error);
    return false;
  }
};

// Helper function to format file size
const formatFileSize = (bytes) => {
  if (bytes === 0) return '0 Bytes';
  const sizes = ['Bytes', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return (bytes / Math.pow(1024, i)).toFixed(2) + ' ' + sizes[i];
};

export const SplatManager = ({
  playerPosition,
  onSplatSelection,
  selectedSplat,
  onTeleport,
  onSplatListUpdate,
  onUpdateSplatProperty
}) => {
  const [uploadingSplat, setUploadingSplat] = useState(false);
  const [nearbySplats, setNearbySplats] = useState([]);
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const [isReplaceModalOpen, setIsReplaceModalOpen] = useState(false);
  const [splatToReplace, setSplatToReplace] = useState(null);
  const lastFetchPosition = useRef(null);

  useEffect(() => {
    // Only fetch if we've moved significantly (e.g., more than 100 meters)
    const shouldFetch = !lastFetchPosition.current ||
      Math.abs(lastFetchPosition.current.lat - playerPosition.lat) > 0.001 ||
      Math.abs(lastFetchPosition.current.lng - playerPosition.lng) > 0.001;

    if (!shouldFetch) return;

    const fetchNearbySplats = async () => {
      try {
        const splatsSnapshot = await getDocs(collection(db, 'splats'));
        const splatsData = splatsSnapshot.docs.map(doc => {
          const data = doc.data();
          // Ensure hidden property is defined (default to false)
          return {
            id: doc.id,
            ...data,
            hidden: data.hidden !== undefined ? data.hidden : false
          };
        });

        setNearbySplats(splatsData);
        lastFetchPosition.current = playerPosition;

        if (selectedSplat && !selectedSplat._editing) {
          const updatedSplat = splatsData.find(splat => splat.id === selectedSplat.id);
          if (updatedSplat) {
            onSplatSelection({
              ...updatedSplat,
              _editing: true
            });
          }
        }
      } catch (error) {
        console.error("Error fetching splats:", error);
      }
    };

    fetchNearbySplats();
  }, [Math.floor(playerPosition.lat * 1000), Math.floor(playerPosition.lng * 1000)]); // Only update when position changes significantly

  const handleUploadSplat = async (splatFile, coordinates, shouldTeleport = true) => {
    setUploadingSplat(true);

    try {
      // Generate unique ID for the splat
      const splatId = Date.now().toString();

      // Upload to Firebase storage
      const splatRef = ref(storage, `splats/${splatId}/${splatFile.name}`);
      const uploadTask = uploadBytesResumable(splatRef, splatFile);

      // Wait for upload to complete
      await uploadTask;

      // Get the download URL
      const downloadURL = await getDownloadURL(splatRef);

      // Create a new document in the splats collection
      const newSplat = {
        id: splatId,
        name: splatFile.name,
        url: downloadURL,
        coordinates: coordinates,
        position: [0, 1, 0],
        rotation: [0, 0, 0],
        scale: [0.5, 0.5, 0.5],
        hidden: false,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString()
      };

      await setDoc(doc(db, 'splats', splatId), newSplat);

      // Update local state
      setNearbySplats(prev => [...prev, newSplat]);
      
      // Notify parent component about the new splat
      if (onSplatListUpdate) {
        onSplatListUpdate([...nearbySplats, newSplat]);
      }

      // Add to local state and select it
      onSplatSelection(newSplat);

      // Only teleport if the flag is true
      if (shouldTeleport) {
        onTeleport(coordinates);
      }

      return newSplat;
    } catch (error) {
      console.error("Error uploading splat:", error);
      throw error;
    } finally {
      setUploadingSplat(false);
    }
  };

  const handleSplatSelection = (splat) => {
    onSplatSelection(splat);
  };

  const deleteSplat = async (splatId) => {
    if (!window.confirm("Are you sure you want to delete this splat?")) return;

    try {
      const splatToDelete = nearbySplats.find(splat => splat.id === splatId);

      // Delete from Firebase Storage if it's a Firebase URL
      if (splatToDelete.url.includes('firebasestorage.googleapis.com')) {
        try {
          const fileRef = ref(storage, splatToDelete.url);
          await deleteObject(fileRef);
        } catch (storageError) {
          console.error("Error deleting from storage:", storageError);
        }
      }

      // Delete from Firestore
      await deleteDoc(doc(db, 'splats', splatId));

      // Update local state
      const updatedSplats = nearbySplats.filter(splat => splat.id !== splatId);
      setNearbySplats(updatedSplats);
      
      // Notify parent component about the deleted splat
      if (onSplatListUpdate) {
        onSplatListUpdate(updatedSplats);
      }

      // If the deleted splat was selected, deselect it
      if (selectedSplat && selectedSplat.id === splatId) {
        onSplatSelection(null);
      }

    } catch (error) {
      console.error("Error deleting splat:", error);
      alert("Failed to delete splat. Please try again.");
    }
  };

  const toggleSplatVisibility = async (splatId) => {
    try {
      // Find the specific splat
      const splatToToggle = nearbySplats.find(splat => splat.id === splatId);
      if (!splatToToggle) {
        console.error("Could not find splat with ID:", splatId);
        return;
      }
      
      // Determine the new state (default to false if hidden is undefined)
      const newHiddenState = !(splatToToggle.hidden || false);
      
      // Update in Firestore - do this first to ensure it's committed
      await updateDoc(doc(db, 'splats', splatId), {
        hidden: newHiddenState,
        updatedAt: new Date().toISOString()
      });
      
      console.log(`Updated splat ${splatId} hidden state to ${newHiddenState} in Firestore`);

      // Check if the toggled splat is the selected one
      if (selectedSplat && selectedSplat.id === splatId) {
        // Use the provided function to update the selected splat
        onUpdateSplatProperty('hidden', newHiddenState);
      } else {
        // If it's not the selected splat, just update the list
        const updatedSplat = { ...splatToToggle, hidden: newHiddenState };
        
        // Update local state
        const updatedSplats = nearbySplats.map(splat => 
          splat.id === splatId ? updatedSplat : splat
        );
        setNearbySplats(updatedSplats);
        
        // Notify parent component with updated splats
        if (onSplatListUpdate) {
          onSplatListUpdate(updatedSplats);
        }
      }
    } catch (error) {
      console.error("Error toggling splat visibility:", error);
      alert("Failed to update splat visibility. Please try again.");
    }
  };

  const handleDownloadSplat = async (splat, e) => {
    e.stopPropagation(); // Prevent splat selection when clicking download
    
    try {
      // Show some feedback to the user that download is in progress
      const button = e.currentTarget;
      const originalContent = button.innerHTML;
      button.innerHTML = '<svg class="animate-spin h-4 w-4" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24"><circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle><path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path></svg>';
      
      // Generate a filename from the splat name or ID
      const filename = splat.name || `splat-${splat.id}.splat`;
      
      // Download the file
      const success = await downloadFile(splat.url, filename);
      
      if (!success) {
        throw new Error("Download failed");
      }
      
      // Restore the button
      setTimeout(() => {
        button.innerHTML = originalContent;
      }, 1000);
      
    } catch (error) {
      console.error("Error downloading splat:", error);
      alert("Failed to download splat file. Please try again.");
    }
  };

  const handleReplaceSplat = (splat, e) => {
    e.stopPropagation(); // Prevent splat selection when clicking replace
    setSplatToReplace(splat);
    setIsReplaceModalOpen(true);
  };

  const processSplatReplacement = async (newSplatFile, originalSplat) => {
    setUploadingSplat(true);

    try {
      // Get original splat reference
      const originalSplatStoragePath = originalSplat.url.split('.com/o/')[1]?.split('?')[0];
      let originalSplatRef = null;
      
      if (originalSplatStoragePath) {
        // Decode the URL-encoded path
        originalSplatRef = ref(storage, decodeURIComponent(originalSplatStoragePath));
      }

      // Upload new splat file with the same ID
      const splatId = originalSplat.id;
      const splatRef = ref(storage, `splats/${splatId}/${newSplatFile.name}`);
      const uploadTask = uploadBytesResumable(splatRef, newSplatFile);

      // Wait for upload to complete
      await uploadTask;

      // Get the download URL
      const downloadURL = await getDownloadURL(splatRef);

      // Update the document in Firestore
      const updatedSplat = {
        ...originalSplat,
        name: newSplatFile.name,
        url: downloadURL,
        updatedAt: new Date().toISOString()
      };

      // Remove id field before updating doc
      const { id, ...splatWithoutId } = updatedSplat;
      
      await updateDoc(doc(db, 'splats', splatId), splatWithoutId);

      // Try to delete the old file if we have a reference
      if (originalSplatRef) {
        try {
          await deleteObject(originalSplatRef);
        } catch (deleteError) {
          console.warn("Could not delete original file:", deleteError);
          // Continue with the update even if delete fails
        }
      }

      // Update local state
      const updatedSplats = nearbySplats.map(s => 
        s.id === splatId ? updatedSplat : s
      );
      
      setNearbySplats(updatedSplats);
      
      // Notify parent component
      if (onSplatListUpdate) {
        onSplatListUpdate(updatedSplats);
      }

      // If the replaced splat was selected, update selection
      if (selectedSplat && selectedSplat.id === splatId) {
        onSplatSelection({
          ...updatedSplat,
          _editing: selectedSplat._editing
        });
      }

      return updatedSplat;
    } catch (error) {
      console.error("Error replacing splat:", error);
      throw error;
    } finally {
      setUploadingSplat(false);
      setSplatToReplace(null);
      setIsReplaceModalOpen(false);
    }
  };

  return (
    <>
      <div className="absolute top-5 right-5 z-10 bg-white p-5 rounded-xl shadow-xl w-96 h-[90vh] flex flex-col">
        <div className="flex justify-between items-center mb-4 pb-3 border-b border-gray-100">
          <h2 className="font-medium text-gray-800">
            <span className="text-sm text-gray-500">Nearby Splats</span><br />
            {nearbySplats.length} found
          </h2>
          <button
            className="bg-blue-500 hover:bg-blue-600 text-white rounded-md px-3 py-2 text-sm transition-colors duration-200"
            onClick={() => setIsUploadModalOpen(true)}
            disabled={uploadingSplat}
          >
            {uploadingSplat ? 'Uploading...' : 'Upload Splat'}
          </button>
        </div>

        <div className="flex-grow overflow-y-auto pr-1 space-y-3">
          {nearbySplats.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-gray-400 text-center">
              <svg xmlns="http://www.w3.org/2000/svg" className="h-12 w-12 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M9 22V12h6v10" />
              </svg>
              <p>No splats found nearby.<br />Upload a splat file to view 3D content.</p>
            </div>
          ) : (
            nearbySplats.map((splat) => (
              <div
                key={splat.id}
                className={`p-3 border rounded-lg cursor-pointer hover:bg-gray-50 transition-colors ${selectedSplat && selectedSplat.id === splat.id ? 'border-blue-500 bg-blue-50' : 'border-gray-200'
                  }`}
                onClick={() => handleSplatSelection(splat)}
              >
                <div className="flex justify-between items-start">
                  <div className="flex-1 min-w-0 mr-3">
                    <div className="font-medium text-sm overflow-hidden" title={splat.name || `Splat ${splat.id}`}>
                      <span className="block truncate">{splat.name || `Splat ${splat.id}`}</span>
                    </div>
                    <div className="text-xs text-gray-500">
                      {new Date(splat.createdAt).toLocaleDateString()}
                    </div>
                    <div className="text-xs text-gray-500">
                      Lat: {splat.coordinates?.lat.toFixed(4)}, Lng: {splat.coordinates?.lng.toFixed(4)}
                    </div>
                  </div>
                  <div className="flex items-center flex-shrink-0">
                    {/* Download button */}
                    <button
                      className="text-green-500 hover:text-green-700 bg-white rounded-full p-1 hover:bg-green-50 transition-colors mr-1"
                      onClick={(e) => handleDownloadSplat(splat, e)}
                      title="Download Splat"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                      </svg>
                    </button>
                    
                    {/* Replace button */}
                    <button
                      className="text-orange-500 hover:text-orange-700 bg-white rounded-full p-1 hover:bg-orange-50 transition-colors mr-1"
                      onClick={(e) => handleReplaceSplat(splat, e)}
                      title="Replace Splat"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                      </svg>
                    </button>
                    
                    {/* Visibility toggle button */}
                    <button
                      className={`${splat.hidden ? 'text-gray-500 hover:text-gray-700' : 'text-blue-500 hover:text-blue-700'} bg-white rounded-full p-1 hover:bg-blue-50 transition-colors mr-1`}
                      onClick={(e) => {
                        e.stopPropagation();
                        toggleSplatVisibility(splat.id);
                      }}
                      title={splat.hidden ? "Show Splat" : "Hide Splat"}
                    >
                      {splat.hidden ? (
                        // Eye Off icon (hidden)
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"></path>
                          <line x1="1" y1="1" x2="23" y2="23"></line>
                        </svg>
                      ) : (
                        // Eye icon (visible)
                        <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path>
                          <circle cx="12" cy="12" r="3"></circle>
                        </svg>
                      )}
                    </button>
                    
                    {/* Delete button */}
                    <button
                      className="text-red-500 hover:text-red-700 bg-white rounded-full p-1 hover:bg-red-50 transition-colors"
                      onClick={(e) => {
                        e.stopPropagation();
                        deleteSplat(splat.id);
                      }}
                      title="Delete Splat"
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                    </button>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      <UploadModal
        isOpen={isUploadModalOpen}
        onClose={() => setIsUploadModalOpen(false)}
        onUpload={handleUploadSplat}
        playerPosition={playerPosition}
      />

      <ReplaceModal
        isOpen={isReplaceModalOpen}
        onClose={() => {
          setIsReplaceModalOpen(false);
          setSplatToReplace(null);
        }}
        originalSplat={splatToReplace}
        onReplace={processSplatReplacement}
      />
    </>
  );
};

// Replace Modal Component
const ReplaceModal = ({ isOpen, onClose, originalSplat, onReplace }) => {
  const [newSplatFile, setNewSplatFile] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  
  const fileInputRef = useRef(null);

  // Reset state when modal opens/closes
  useEffect(() => {
    if (!isOpen) {
      setNewSplatFile(null);
      setError(null);
    }
  }, [isOpen]);

  const handleFileSelect = (e) => {
    if (e.target.files.length > 0) {
      setNewSplatFile(e.target.files[0]);
    }
  };

  const handleReplace = async () => {
    if (!newSplatFile) {
      setError("Please select a new splat file");
      return;
    }

    try {
      setIsLoading(true);
      setError(null);
      await onReplace(newSplatFile, originalSplat);
      onClose();
    } catch (err) {
      setError(`Failed to replace splat: ${err.message}`);
      setIsLoading(false);
    }
  };

  if (!isOpen || !originalSplat) return null;

  // Format file size for display
  const newFileSize = newSplatFile ? formatFileSize(newSplatFile.size) : '';

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white p-5 rounded-lg shadow-xl w-full max-w-md">
        {/* Header */}
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-medium">Replace Splat</h2>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-700"
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Error message if any */}
        {error && (
          <div className="mb-4 p-2 bg-red-100 text-red-700 rounded-md text-sm">
            {error}
          </div>
        )}

        {/* Original Splat Section */}
        <div className="bg-blue-50 p-3 rounded-md mb-4">
          <div className="text-xs font-medium text-blue-800">Original Splat</div>
          <div className="text-sm mt-1 truncate" title={originalSplat.name}>
            {originalSplat.name}
          </div>
        </div>

        {/* New File Selection */}
        <div className="mb-4">
          <div className="flex items-center justify-between">
            <button
              onClick={() => fileInputRef.current.click()}
              className="bg-orange-50 border border-orange-300 rounded px-3 py-1.5 text-sm hover:bg-orange-100"
            >
              Select File
            </button>
            <div className="ml-3 text-sm text-gray-500 flex-1 truncate">
              {newSplatFile ? (
                <div className="flex items-center">
                  <span className="truncate" title={newSplatFile.name}>
                    {newSplatFile.name}
                  </span>
                  <span className="ml-2 text-xs text-gray-400 whitespace-nowrap">
                    {newFileSize}
                  </span>
                </div>
              ) : (
                'No file selected'
              )}
            </div>
            <input
              ref={fileInputRef}
              type="file"
              accept=".splat"
              onChange={handleFileSelect}
              className="hidden"
            />
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex justify-end">
          <button
            onClick={onClose}
            className="px-3 py-1.5 bg-gray-200 text-gray-800 rounded text-sm font-medium hover:bg-gray-300 mr-2"
          >
            Cancel
          </button>
          <button
            onClick={handleReplace}
            className="px-3 py-1.5 bg-orange-600 text-white rounded text-sm font-medium hover:bg-orange-700 disabled:opacity-50"
            disabled={!newSplatFile || isLoading}
          >
            {isLoading ? 'Replacing...' : 'Replace Splat'}
          </button>
        </div>
      </div>
    </div>
  );
}; 