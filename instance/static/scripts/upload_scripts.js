document.getElementById('uploadForm').onsubmit = function(event) {
    event.preventDefault();  // Prevent the form from submitting the default way (which reloads the page)

    // Get form and elements
    const form = document.getElementById('uploadForm');
    const formData = new FormData(form);
    
    // Show upload progress bar
    document.getElementById('uploadProgressContainer').style.display = 'block';
    const uploadProgressBar = document.getElementById('uploadProgress');
    
    // Create new XMLHttpRequest for AJAX
    const xhr = new XMLHttpRequest();

    // Monitor the upload progress event
    xhr.upload.onprogress = function(e) {
        if (e.lengthComputable) {
            const percentComplete = (e.loaded / e.total) * 100;
            uploadProgressBar.style.width = percentComplete + '%';
            uploadProgressBar.textContent = Math.round(percentComplete) + '%';
        }
    };

    // Handle server response
    xhr.onload = function() {
        if (xhr.status === 200) {
            // Parse the response
            const response = JSON.parse(xhr.responseText);
            uploadProgressBar.textContent = "Upload Complete!";

            // Check if job_id is present in the response (for video encoding)
            if (response.job_id) {
                // Start polling for encoding progress
                let encodingProgressBar = document.getElementById('encodingProgress');
                document.getElementById('encodingProgressContainer').style.display = 'block';
                let interval = setInterval(() => {
                    fetch(`/encoding_progress/${response.job_id}`)
                        .then(res => res.json())
                        .then(data => {
                            if (data.progress) {
                                encodingProgressBar.style.width = data.progress + '%';
                                encodingProgressBar.textContent = data.progress + '%';

                                // Handle completion
                                if (data.status === 'completed') {
                                    clearInterval(interval);
                                    encodingProgressBar.textContent = "Encoding Complete!";
                                    
                                    // Redirect after encoding completes
                                    setTimeout(function() {
                                        window.location.href = "/gallery";
                                    }, 2000);  // 2-second delay for user to see the message
                                }
                            }
                        })
                        .catch(error => console.error('Error fetching encoding progress:', error));
                }, 1000);  // Poll every second
            } else {
                // Handle success for images (no job_id)
                uploadProgressBar.textContent = "Image uploaded successfully!";
                document.getElementById('encodingProgressContainer').style.display = 'none'; // Hide encoding progress

                // Redirect after image upload completes
                setTimeout(function() {
                    window.location.href = "/gallery";
                }, 2000);  // 2-second delay for user to see the message
            }
        } else {
            const errorResponse = JSON.parse(xhr.responseText);
            uploadProgressBar.textContent = errorResponse.error || "Upload Failed!";
        }
    };

    // Handle errors in upload
    xhr.onerror = function() {
        uploadProgressBar.textContent = "Error occurred during upload.";
    };

    // Set the POST URL and start the request
    xhr.open('POST', form.action, true);
    xhr.send(formData);
};
