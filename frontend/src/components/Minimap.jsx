import React from 'react';

/**
 * Minimap component for displaying the player's position on a map.
 * 
 * @param {Object} props
 * @param {string} props.currentChunk - Current chunk ID
 * @param {Set} props.platforms - Set of loaded platform IDs
 * @param {Object} props.playerPosition - {x, z} coordinates of the player
 * @param {Object} props.data - Map data with textures
 * @param {number} props.chunkSize - Size of each chunk
 * @param {Object} props.playerDirection - Direction the player is facing
 */
const Minimap = ({ currentChunk, platforms, playerPosition, data, chunkSize, playerDirection }) => {
  // Calculate minimap dimensions
  const minimapSize = 200; // px
  
  // Scale factor to convert from world units to pixels - higher means more zoomed in
  const scaleFactor = 10; // Increased for better visibility and responsiveness
  
  // Extract map tile images from textures
  const getMapTileUrl = (texture) => {
    if (!texture) return null;
    return texture.source.data.src; // Extract the image URL from the Three.js texture
  };

  return (
    <div className="absolute right-5 bottom-5 z-10 bg-white bg-opacity-90 rounded-lg shadow-md overflow-hidden">
      <div className="p-2 bg-gray-800 text-white text-xs font-medium">
        Minimap - Current Chunk: {currentChunk}
      </div>
      <div 
        style={{ width: `${minimapSize}px`, height: `${minimapSize}px` }} 
        className="relative border border-gray-400 overflow-hidden bg-gray-100"
      >
        {/* Map container that moves under the fixed player */}
        <div 
          className="absolute"
          style={{
            // Position the map container in the center of the minimap
            width: 0,
            height: 0,
            left: `${minimapSize / 2}px`,
            top: `${minimapSize / 2}px`,
            // Apply inverse of player movement to make the map scroll beneath
            transform: `translate(${-playerPosition.x * scaleFactor}px, ${-playerPosition.z * scaleFactor}px)`,
            transition: 'transform 0.1s linear',
          }}
        >
          {/* Render loaded chunks/platforms */}
          {[...platforms].map(pos => {
            const [chunkX, chunkZ] = pos.split(',').map(Number);
            const tileData = data[pos]; // Get the tile data for this chunk
            const tileImageUrl = tileData ? getMapTileUrl(tileData.texture) : null;
            
            // Calculate absolute position in world space
            const worldX = chunkX * chunkSize;
            const worldZ = chunkZ * chunkSize;
            
            // Scaled coordinates in pixels
            const scaledX = worldX * scaleFactor;
            const scaledZ = worldZ * scaleFactor;
            const scaledSize = chunkSize * scaleFactor;

            return (
              <div 
                key={`minimap-chunk-${pos}`}
                style={{
                  position: 'absolute',
                  // Position relative to the map container's center
                  left: `${scaledX}px`,
                  top: `${scaledZ}px`,
                  width: `${scaledSize}px`,
                  height: `${scaledSize}px`,
                  border: '1px solid rgba(0, 0, 0, 0.3)',
                  overflow: 'hidden',
                  backgroundColor: tileData ? 'transparent' : 'rgba(200, 200, 200, 0.5)',
                  // Position from top-left corner of the chunk
                  transform: 'translate(-50%, -50%)', 
                }}
              >
                {tileImageUrl ? (
                  <img 
                    src={tileImageUrl} 
                    alt={`Map tile ${pos}`}
                    className="w-full h-full object-cover"
                    style={{ 
                      transition: 'opacity 0.3s ease-in-out',
                      opacity: tileData ? 1 : 0 
                    }}
                    onLoad={(e) => {
                      // Add a fade-in effect when images load
                      e.target.style.opacity = '1';
                    }}
                  />
                ) : (
                  <div className="text-[8px] text-center mt-4 text-gray-500 transition-opacity duration-300">
                    {chunkX},{chunkZ}
                  </div>
                )}
              </div>
            );
          })}
        </div>
        
        {/* Debug info */}
        <div className="absolute bottom-1 left-1 text-[8px] text-black bg-white bg-opacity-60 p-1 rounded">
          Player: ({playerPosition.x.toFixed(1)}, {playerPosition.z.toFixed(1)})
        </div>
        
        {/* Fixed player position indicator - always centered */}
        <div 
          style={{
            position: 'absolute',
            left: '50%',
            top: '50%',
            width: '8px',
            height: '8px',
            backgroundColor: 'red',
            borderRadius: '50%',
            transform: 'translate(-50%, -50%)',
            zIndex: 10,
            boxShadow: '0 0 0 2px white, 0 0 4px 1px black',
          }}
        />
      </div>
    </div>
  );
};

export default Minimap; 