let modal = document.getElementById("mediaModal");
let modalImg = document.getElementById("modalImage");
let modalVideo = document.getElementById("modalVideo");
let videoSource = document.getElementById("videoSource");
let shareButton = document.getElementById("shareButton");
let player;

function deleteMedia(uploadId) {
    // Confirm with the user before deleting
    if (!confirm("Are you sure you want to delete this media?")) {
        return;
    }

    // Send a POST request to the server
    fetch(`/delete_upload/${uploadId}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/x-www-form-urlencoded',  // Required for form submission via fetch
            'X-CSRFToken': getCSRFToken()  // If CSRF protection is enabled, get the token if necessary
        },
    })
    .then(response => {
        if (response.ok) {
            alert('Media deleted successfully.');
            // Optionally remove the media element from the DOM
            document.getElementById(`media-${uploadId}`).remove();
        } else {
            alert('Failed to delete the media.');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('An error occurred while deleting the media.');
    });
}

// Helper function to get the CSRF token if your app uses it
function getCSRFToken() {
    let csrfToken = document.querySelector('meta[name="csrf-token"]');
    return csrfToken ? csrfToken.getAttribute('content') : '';
}


function openModal(src, type, id, shareToken) {
    modal.style.display = "flex";  // Show the modal
    shareButton.style.display = "block";  // Show the share button

    // Set the share button's onclick dynamically
    shareButton.setAttribute("onclick", `shareMedia(${id})`);

    // Show the Discord share button
    const discordButton = document.getElementById('shareDiscordButton');
    discordButton.style.display = "block"; // Show the button
    discordButton.setAttribute("onclick", `openDiscordShareModal(${id}, '${shareToken}')`); // Set the onclick

    if (type === 'image') {
        modalImg.style.display = "block";
        modalVideo.parentElement.style.display = "none";
        modalImg.src = src;
    } else if (type === 'video') {
        modalImg.style.display = "none";
        modalVideo.parentElement.style.display = "block";
        
        // Set the video source and load the player
        videoSource.src = src;
        modalVideo.load();

        // Initialize Video.js (make sure this is only done once)
        if (!player) {
            player = videojs(modalVideo, {
                controls: true,
                preload: 'auto',
                techOrder: ['html5'],
                fluid: true,
            });
        } else {
            player.src(src);  // If the player is already initialized, just change the source
        }
    }
}

function shareMedia(uploadId) {
    fetch(`/generate_share_token/${uploadId}`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRF-Token': '{{ csrf_token() }}'  // Ensure you have CSRF protection enabled
        }
    })
    .then(response => {
        if (response.ok) {
            return response.json();
        } else {
            throw new Error('Failed to generate share token');
        }
    })
    .then(data => {
        const shareUrl = `https://breadgameserver.duckdns.org/media/${data.share_token}`;
        const embedURL = `[▻](https://breadgameserver.duckdns.org/media/${data.share_token})`;
        navigator.clipboard.writeText(embedURL)
            .then(() => {
                alert('Share URL copied to clipboard: ' + shareUrl);
            })
            .catch(err => {
                console.error('Could not copy text: ', err);
            });
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Failed to generate share token. Please try again.');
    });
}

function openDiscordShareModal(uploadId, uploadTitle) {
    document.getElementById('uploadId').value = uploadId; // Set the hidden upload ID
    //document.getElementById('uploaderName').value = uploadTitle; // Optionally set the uploader name or any relevant information
    document.getElementById('discordShareModal').style.display = 'block'; // Show the modal
}

function closeDiscordShareModal() {
    document.getElementById('discordShareModal').style.display = 'none'; // Hide the modal
    document.getElementById('uploaderName').value = ''; // Reset uploader name field
    document.getElementById('discordChannelID').value = ''; // Reset discord channel ID field
    document.getElementById('uploadId').value = ''; // Reset upload ID field
}

function submitDiscordShare() {
    const uploaderName = document.getElementById("uploaderName").value;
    const discordChannelID = document.getElementById("discordChannelID").value;
    const uploadId = document.getElementById("uploadId").value; // Get the hidden upload ID

    // Make a POST request to your Flask route for sharing in Discord
    fetch('/share_discord', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            uploader_name: uploaderName,
            discord_channel_id: discordChannelID,
            upload_id: uploadId  // Include the upload ID here
        }),
    })
    .then(response => {
        if (response.ok) {
            alert("Shared successfully in Discord! Can take a little bit to show up, wait a minute or so.");
            closeDiscordShareModal();
        } else {
            alert("Error sharing in Discord.");
        }
    })
    .catch(error => {
        console.error("Error:", error);
    });
}

function closeModal() {
    console.log("Closing modal");
    modal.style.display = "none"; // Hide the modal

    // Pause and reset the video when closing
    if (player) {
        console.log("Pausing and clearing video source");
        player.pause();
        player.src(""); // Clear the video source to stop playback
    }
}
