from flask import Flask, render_template, request, redirect, url_for

from flask import jsonify

import subprocess
import os
import psutil
import time
from datetime import datetime
import socket
import json
import shutil



from flask import Flask, render_template, request, redirect, session, url_for, flash
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import timedelta
from functools import wraps

import config


app = Flask(__name__)
app.secret_key = 'super-secret-key'  # use a strong key in real use
app.permanent_session_lifetime = timedelta(minutes=30)  # idle timeout

def get_system_uptime():
    try:
        uptime = subprocess.check_output(['uptime', '-p']).decode('utf-8').strip()
        return uptime.replace('up ', '')
    except:
        return "N/A"

def get_connected_users():
    try:
        users = subprocess.check_output(['who', '-q']).decode('utf-8').splitlines()[0]
        if users[0] == '#': 
            return users.split('=')[1]
        else:
            users2= users.strip()
            return len(users2.split())
    except:
        return "0"


def get_ip_address():
    """
    Determines the local IP address by iterating through network interfaces
    using psutil, excluding loopback and common virtual interfaces.
    """
    interfaces = psutil.net_if_addrs()
    for interface_name, addresses in interfaces.items():
        # Skip loopback and common virtual/docker interfaces
        if interface_name.startswith('lo') or \
           interface_name.startswith('docker') or \
           interface_name.startswith('veth') or \
           interface_name.startswith('br-') or \
           interface_name.startswith('dummy'): # Add dummy if present
            continue

        for addr in addresses:
            if addr.family == socket.AF_INET: # IPv4 address
                # Exclude link-local (APIPA) addresses (169.254.0.0/16)
                if not addr.address.startswith('169.254.'):
                    return addr.address
    return "N/A (No suitable IP found)"
        


#=================================================   login  =============================================================

# Hardcoded single user
USER = {
    'username': config.admin_name ,
    'password_hash': generate_password_hash(config.admin_pw)  # only store hashed password
}


# Decorator to protect routes


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'username' not in session:
            flash('Login required', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapper
    
    
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if username == USER['username'] and check_password_hash(USER['password_hash'], password):
            session.permanent = True
            session['username'] = username
            flash('Logged in successfully!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'danger')
            return render_template('login.html')
    
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out', 'info')
    return redirect(url_for('login'))


#=================================================   login  ============================================================= 
 
@app.route('/')
@login_required
def dashboard():
    return render_template('dashboard.html',
                         uptime=get_system_uptime(),
                         users_connected=get_connected_users(),
                         ip_address=get_ip_address(),
                         current_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                         
                         username=session['username'])    


@app.route('/refresh')
@login_required
def refresh():
    return {
        'uptime': get_system_uptime(),
        'users_connected': get_connected_users()
    }

@app.route('/api/shutdown', methods=['POST'])
@login_required
def shutdown():
    # In production: os.system('sudo shutdown -h now')
    print("Shutdown command received")  # Replace with actual command
    os.system('sudo shutdown -h now')
    
    return jsonify({'success': True})

@app.route('/api/reboot', methods=['POST'])
@login_required
def reboot():
    # In production: os.system('sudo reboot')
    print("Reboot command received")  # Replace with actual command
    os.system('sudo reboot')
    #subprocess.run(['sudo', 'reboot'], check=True)
    return jsonify({'success': True})


def get_cpu_temp():
    try:
        temps = psutil.sensors_temperatures()
        cpu_temp_found = False
        temp_val = ''
        for name, entries in temps.items():
            for entry in entries:
                if 'cpu' in name.lower() or 'coretemp' in name.lower(): # Common names for CPU temps
                    temp_val = f"{entry.current}°C"
                    cpu_temp_found = True
                    break
            if cpu_temp_found:
                break
        if not cpu_temp_found:
            temp_val = "N/A (lm-sensors not detected or configured)"
        return temp_val

    except:
        return "N/A"

def get_cpu_usage():
    try:
        
        # # # print(f"{psutil.cpu_percent(interval=1)}%")
        return f"{psutil.cpu_percent(interval=1)}%"
    except:
        return "N/A"

@app.route('/system_stats')
@login_required
def system_stats():
    return jsonify({
        'cpu_temp': get_cpu_temp(),
        'cpu_usage': get_cpu_usage()
    })

@app.route('/api/usb-drives')
@login_required 
def usb_drives():
    try:
        result = subprocess.check_output([
            'lsblk', '-J', '-o', 'NAME,MOUNTPOINT,RM,TRAN,SIZE,LABEL,VENDOR,MODEL,fstype'
        ]).decode()
        lsblk_data = json.loads(result)
        devices = []
        for dev in lsblk_data['blockdevices']:
            if dev.get('tran') == 'usb':
                for partition in dev.get('children', []) :
                    if  'G' in partition.get('size') : ## if partition size > 1GB
                        drive_info = {
                            'device': dev['name'],
                            'partition':partition['name'],
                            'mountpoint': partition.get('mountpoint') or '',
                            'size': partition.get('size') or '',
                            'label': partition.get('label') or '',
                            'vendor': dev.get('vendor') or '',
                            'model': dev.get('model') or '',
                            'fstype': partition.get('fstype') or '',
                            'usage': None
                        }
                       
                       # Add usage stats if mounted
                        if partition.get('mountpoint'):  #is not None basically
                            try:
                                usage = shutil.disk_usage(partition['mountpoint'])
                                drive_info['usage'] = {
                                    'total': usage.total,
                                    'used': usage.used,
                                    'free': usage.free,
                                    'percent': "{:.2f}".format (usage.used / usage.total * 100)
                                }
                            except Exception as e:
                                print(f"Couldn't get usage for {partition['mountpoint']}: {e}")
                        devices.append (drive_info)
        # # # print (devices)
        return jsonify(devices)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
 
def get_partition_uuid(device):
    try:
        result = subprocess.run(
            ['sudo', 'blkid', '-s', 'UUID', '-o', 'value', f'/dev/{device}'],
            capture_output=True, text=True, check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return None

@app.route('/mount/<device>')
@login_required
def mount_drive(device):
    mode = request.args.get('mode', 'private')  # default to private
    if mode == 'private':
        base_dir = '/mnt/ext_drive_pvt/' 
        uuid = get_partition_uuid(device)
        if not uuid:
            return jsonify({
                'success': False,
                'error': f"Could not find UUID for /dev/{device}"
            }), 400
        mount_point = base_dir + str(uuid)
    else:
        base_dir = '/mnt/ext_drive1/'
        mount_point = base_dir + str(device)
    
    
    
    try:
        # Create mount point directory
        
        subprocess.run(['sudo', 'mkdir', '-p', mount_point], check=True)
        
        # Mount the device
        subprocess.run(['sudo', 'mount', f"/dev/{device}", mount_point], check=True)
        
        return jsonify({
            'success': True,
            'message': f"Successfully mounted /dev/{device} at {mount_point}",
            'mountpoint': mount_point
        })
    except subprocess.CalledProcessError as e:
        return jsonify({
            'success': False,
            'error': f"Failed to mount /dev/{device}: {str(e)}"
        }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f"Unexpected error: {str(e)}"
        }), 500

@app.route('/umount/<path:mountpoint>')
@login_required
def unmount_drive(mountpoint):
    try:
        # Unmount the device
        # Ensure path starts with /
        if not mountpoint.startswith('/'):
            mountpoint = f'/{mountpoint}'
            
        # # # print (mountpoint)
        subprocess.run(['sudo', 'umount', mountpoint], check=True)
        
        # Optionally: Remove the mount point directory
        subprocess.run(['sudo', 'rmdir', mountpoint], check=True)
        
        return jsonify({
            'success': True,
            'message': f"Successfully unmounted {mountpoint}"
        })
    except subprocess.CalledProcessError as e:
        return jsonify({
            'success': False,
            'error': f"Failed to unmount {mountpoint}: {str(e)}"
        }), 400
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f"Unexpected error: {str(e)}"
        }), 500


def sizeof_fmt(num):
    """Convert bytes to human-readable format"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if num < 1024.0:
            return f"{num:.1f} {unit}"
        num /= 1024.0
    return f"{num:.1f} PB"
 
@app.route('/api/int_part-usage')
@login_required
def sda6_usage():
    try:
        # Get detailed usage stats for sda6
        result = subprocess.run(
            ['df', '--block-size=1', '--output=size,used,avail,pcent', config.Internal_partition_path ],
            capture_output=True,
            text=True
        )
        
        result2 = subprocess.run(
            ['findmnt', '-n', '-o', 'SOURCE', '--target', config.Internal_partition_path ],
            capture_output=True,
            text=True
        )
        path = result2.stdout.strip().split('\n')
        print (path)
        
        if result.returncode == 0:
            # Parse df output (header + data)
            lines = result.stdout.strip().split('\n')
            if len(lines) >= 2:
                size, used, free, pct = lines[1].split()
                size, used, free = int(size), int(used), int(free)
                # # # # print (lines[1])
                return jsonify({
                    'total': sizeof_fmt(size),
                    'used': sizeof_fmt(used ),  # df returns 1K blocks
                    'usage_percent': int(pct.replace('%', '')),
                    'free': sizeof_fmt(free),
                    'path': path
                })
        
        return jsonify({'error': 'Could not get usage data'}), 400
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500




if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')   