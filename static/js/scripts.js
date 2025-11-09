function refreshData() {
	fetch('/refresh')
		.then(response => response.json())
		.then(data => {
			document.querySelector('.status-value:nth-of-type(1)').textContent = data.uptime;
			document.querySelector('.status-value:nth-of-type(2)').textContent = data.users_connected;
			document.getElementById('last-updated').textContent = new Date().toLocaleString();
		});
}



function confirmShutdown() {
    if (confirm("WARNING: This will immediately shutdown the server. Continue?")) {
        fetch('/api/shutdown', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Simple fade-out effect instead of goodbye message
                document.body.style.opacity = '0.5';
                document.body.style.transition = 'opacity 1s';
            }
        })
        .catch(error => console.error('Error:', error));
    }
}

function confirmReboot() {
    if (confirm("This will reboot the server. Continue?")) {
        fetch('/api/reboot', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
    }
}

function refreshSystemStats() {
    fetch('/system_stats')
        .then(response => response.json())
        .then(data => {
            document.getElementById('cpu-temp').textContent = data.cpu_temp;
            document.getElementById('cpu-usage').textContent = data.cpu_usage;
            
            // Add warning if temperature is high
            const temp = parseFloat(data.cpu_temp);
            const warning = document.getElementById('temp-warning');
            warning.textContent = '';
            
            if (!isNaN(temp)) {
                if (temp > 80) {
                    warning.textContent = '⚠️ High temperature!';
                    warning.style.color = '#e74c3c';
                } else if (temp > 60) {
                    warning.textContent = '⚠️ Temperature rising';
                    warning.style.color = '#f39c12';
                }
            }
        });
}

// Initial load
document.addEventListener('DOMContentLoaded', refreshSystemStats);

//  FOllowing are for usb drives

function formatBytes(bytes) {
    // Handle invalid inputs like null, undefined, 0, or non-numbers
    if (bytes === null || bytes === undefined || isNaN(bytes) || bytes === 0) {
        return '0 Bytes';
    }

    // Ensure bytes is a positive number for Math.log
    if (bytes < 0) {
        return '-' + formatBytes(Math.abs(bytes)); // Recursively handle absolute value and prepend '-'
    }

    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB']; 
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return (bytes / Math.pow(k, i)).toFixed(1) + ' ' + sizes[i];
}




function loadDrives() {
    const container = document.getElementById('drives-container');
    container.innerHTML = '<p class="loading">Checking for drives...</p>';
    
    fetch('/api/usb-drives')
        .then(res => res.json())
        .then(data => {
            container.innerHTML = '';
            
            if (data.length === 0) {
                container.innerHTML = '<p class="no-drives">No USB drives found</p>';
                return;
            }
            
            data.forEach(dev => {
                const div = document.createElement('div');
                div.className = 'drive';
                
                // Build the info string
                let info = `<strong>${dev.vendor || 'Unknown Brand'}`;
                if (dev.model) info += ` ${dev.model}`;
                info += `</strong>`;
                info += `<span>${dev.size}`;
                if (dev.label) info += ` • ${dev.label}  `;
                info += `</span>`;
                info += `<span class="device-path">/dev/${dev.partition} • ${dev.fstype}</span>`;

                let usageHTML = '';
                if (dev.mountpoint && dev.usage) {
					
                    usageHTML = `
                        <div class="usage">
                            <div class="usage-bar">
                                <div class="usage-fill" style="width: ${dev.usage.percent}%"></div>
                            </div>
                            <div class="usage-stats-leftright">
                                <span>used ${formatBytes(dev.usage.used)} / ${formatBytes(dev.usage.total)} • (${dev.usage.percent}%)</span> 
                                <span class="free-text">free ${formatBytes(dev.usage.free)} </span>
                            </div>
					</div>
                        </div>
                    `;
                }     
					div.innerHTML = `
                    <div class="drive-info">
                        ${info}
						${usageHTML}
                    </div>
                    <div class="drive-actions">
                        ${dev.mountpoint ? `
                            <span class="mounted">Mounted</span>
                            <button class="btn-warning-4drive" 
                                    onclick="unmountDrive('${dev.mountpoint}')">
                                Unmount
                            </button>
                        ` : `
                            <button class="btn-secondary-4drive" 
                                    onclick="mountDrive('${dev.partition}')">
                                Mount
                            </button>
                            <button class="btn-secondary-4drive" 
                                    onclick="mountDrive_private('${dev.partition}')">
                                Mount private
                            </button>


                        `}
                    </div>
                `;
                
                container.appendChild(div);
            });
        })
        .catch(error => {
            container.innerHTML = `
                <p class="error">Error loading drives</p>
                <button onclick="loadDrives()">Try Again</button>
            `;
        });
}

// Keep your existing mountDrive() and unmountDrive() functions

function mountDrive(partition) {  // Now receives partition (e.g. "sdb1")
    if (confirm(`Mount /dev/${partition} in public share folder ?`)) {
        fetch(`/mount/${partition}?mode=public`)
            .then(loadDrives)
            .catch(alert);
    }
}

function mountDrive_private(partition) {  // Now receives partition (e.g. "sdb1")
    if (confirm(`Mount /dev/${partition} in private folder ?`)) {
        fetch(`/mount/${partition}?mode=private`)
            .then(loadDrives)
            .catch(alert);
    }
}

function unmountDrive(mountpoint) {
    if (confirm(`Unmount ${mountpoint}?`)) {
        fetch(`/umount/${mountpoint}`)
            .then(loadDrives)
            .catch(alert);
    }
}



document.addEventListener('DOMContentLoaded', function() {
    fetch('/api/int_part-usage')
        .then(response => response.json())
        .then(data => {
            const container = document.getElementById('int_part-container');
            
            if (data.error) {
                container.innerHTML = `<p class="error">Error: ${data.error}</p>`;
                return;
            }
            
			
            container.innerHTML = `
                <div class="drive-usage">
                    <div class="usage-header">
                        <strong>${data.path}</strong>
                        <span>    total size = ${data.total} </span>
                    </div>
                    <div class="usage-bar">
                        <div class="usage-fill" style="width: ${data.usage_percent}%"></div>
                    </div>
					
					<div class="usage-stats-leftright">
						<span>used ${data.used} / ${data.total} • (${data.usage_percent}%)</span>
						<span class="free-text">free ${data.free}</span>
					</div>					
                </div>
            `;
        });
});