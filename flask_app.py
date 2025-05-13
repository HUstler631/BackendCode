#--> Standard module & library
import json
import requests
import urllib.parse
import re
import os
import time
import math
from urllib.parse import urlparse, parse_qs

#--> Flask
from flask import Flask, Response, request, jsonify, redirect
from flask_cors import CORS
app = Flask(import_name=__name__)
CORS(app=app, supports_credentials=True)

#--> Local module
from python.terabox1 import TeraboxFile, TeraboxLink
from python.terabox2 import TeraboxFile as TF2, TeraboxLink as TL2, TeraboxSession as TS

#--> Global Variable
config = {'status':'failed', 'message':'cookie terabox nya invalid bos, coba lapor ke dapunta', 'mode':1, 'cookie':''}

# Function to fetch M3U8 segments from a streaming URL
def fetch_m3u8_segments(url_string, max_attempts=10, delay=2, is_fast_mode=False, return_early=True, min_segments_early=5):
    try:
        # Parse the URL to extract parameters
        parsed_url = urlparse(url_string)
        params = parse_qs(parsed_url.query)
        
        # Convert multivalue dict to single value dict
        params = {k: v[0] for k, v in params.items()}
        
        print(f"[DEBUG] Original URL parameters: {params}")
        
        # Update timestamp parameter
        current_timestamp = int(time.time())
        if 'timestamp' in params:
            params['timestamp'] = str(current_timestamp)
        
        # Headers for request
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
            "Referer": "https://www.1024tera.com/",
            "Accept": "*/*",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive"
        }
        
        # Extract video ID from URL
        video_id = params.get('fid', '')
        if video_id:
            print(f"[DEBUG] Video ID (fid): {video_id}")
            
            # Try direct URL format
            direct_url = f"https://www.1024tera.com/api/streaming?fid={video_id}&type=M3U8_FLV_264_480"
            print(f"[DEBUG] Trying alternative direct URL: {direct_url}")
            
            try:
                direct_response = requests.get(direct_url, headers=headers, timeout=15)
                
                if direct_response.status_code == 200:
                    data = direct_response.text
                    print(f"[DEBUG] Direct URL response preview: {data[:200]}")
                    
                    if '#EXTM3U' in data or '#EXTINF' in data:
                        print("[DEBUG] Successfully received M3U8 content from direct URL!")
                        segments = process_m3u8(data)
                        if segments:
                            return segments
                    else:
                        print("[DEBUG] Direct URL did not return M3U8 content")
            except Exception as error:
                print(f"[DEBUG] Error fetching direct URL: {str(error)}")
        
        # If direct URL failed, try the main URL approach with various start positions
        print("[DEBUG] Trying main URL approach with multiple start positions...")
        
        segments = {}
        seen_urls = set()
        segment_indices = set()
        
        # Generate start positions prioritizing the beginning of the video first
        start_positions = []
        
        # Always start with 0, 5, 10, 15, 20, 25 seconds to get initial segments quickly
        for i in range(0, 31, 5):
            start_positions.append(i)
        
        if is_fast_mode:
            # Fast mode: fewer positions with strategic spacing
            # Beginning (0-5 min)
            for i in range(60, 301, 60):
                start_positions.append(i)
            # Middle (5-10 min)
            for i in range(330, 601, 90):
                start_positions.append(i)
            # End (10-16 min)
            for i in range(660, 961, 120):
                start_positions.append(i)
            
            # Add a few specific positions
            start_positions.extend([940, 950, 960])
        else:
            # Normal mode: more comprehensive coverage
            # First 10 minutes: 30 second intervals
            for i in range(60, 601, 30):
                start_positions.append(i)
            
            # 10-15 minutes: 20 second intervals
            for i in range(620, 901, 20):
                start_positions.append(i)
            
            # Final 3 minutes: 15 second intervals
            for i in range(915, 1081, 15):
                start_positions.append(i)
            
            # Add very specific positions around the 15-16 minute mark
            for i in range(890, 961, 5):
                start_positions.append(i)
            
            # Add extra positions
            start_positions.extend([945, 950, 955, 960, 965, 970, 975, 980, 985, 990, 995, 1000])
        
        print(f"[DEBUG] Generated {len(start_positions)} start positions from 0 to {max(start_positions)} seconds")
        
        # Create a base URL from the parsed URL
        base_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
        
        for position in start_positions:
            # Update timestamp for each new position
            params['timestamp'] = str(int(time.time()))
            
            # Add start_ply parameter
            params['start_ply'] = str(position)
            
            # Reconstruct the URL
            query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
            modified_url = f"{base_url}?{query_string}"
            
            print(f"[DEBUG] Trying with start position: {position} seconds")
            print(f"[DEBUG] URL: {modified_url[:100]}...")
            
            # Maximum attempts for this position
            max_position_attempts = max(1, max_attempts // len(start_positions)) + 1
            
            for attempt in range(max_position_attempts):
                try:
                    response = requests.get(modified_url, headers=headers, timeout=15)
                    
                    response_text = response.text
                    
                    print(f"[DEBUG] Position {position}, Attempt {attempt + 1}: Status {response.status_code}")
                    # Process the text separately from the f-string
                    preview_text = response_text[:100].replace('\n', '[newline]')
                    print(f"[DEBUG] Response preview: {preview_text}")
                    
                    # Check if response is an error
                    if response_text.startswith('{') and 'errno' in response_text:
                        try:
                            error_json = json.loads(response_text)
                            print(f"[DEBUG] Server returned error: {json.dumps(error_json)}")
                            
                            if error_json.get('show_msg') == "invalid timestamp":
                                print("[DEBUG] This URL may be expired or require a valid session")
                            continue
                        except Exception as e:
                            print("[DEBUG] Failed to parse error JSON")
                    
                    # Check if response looks like an M3U8 file
                    if '#EXTM3U' in response_text or '#EXTINF' in response_text:
                        print("[DEBUG] Found valid M3U8 content!")
                        
                        # Process M3U8 content for this position
                        new_segments = process_m3u8(response_text)
                        
                        # Add new segments to our collection
                        for segment_url, segment_info in new_segments.items():
                            if segment_url not in seen_urls:
                                seen_urls.add(segment_url)
                                segments[segment_url] = segment_info
                                segment_indices.add(segment_info['index'])
                        
                        print(f"[DEBUG] Position {position}: Added segments, Total: {len(segments)}")
                        
                        # Return early with initial segments if requested (helps with faster playback)
                        if return_early and len(segments) >= min_segments_early:
                            print(f"[DEBUG] Returning early with {len(segments)} initial segments for faster playback")
                            return segments
                        
                        # If we found new segments, try more positions around this one
                        if len(new_segments) > 0:
                            gap_positions = [
                                position - 30, 
                                position - 15, 
                                position - 5,
                                position + 5,
                                position + 15, 
                                position + 30
                            ]
                            gap_positions = [p for p in gap_positions if p >= 0 and p not in start_positions]
                            
                            for gap_position in gap_positions:
                                params['start_ply'] = str(gap_position)
                                query_string = '&'.join([f"{k}={v}" for k, v in params.items()])
                                gap_url = f"{base_url}?{query_string}"
                                
                                print(f"[DEBUG] Trying to fill gap at position: {gap_position} seconds")
                                
                                try:
                                    gap_response = requests.get(gap_url, headers=headers, timeout=15)
                                    gap_text = gap_response.text
                                    
                                    if '#EXTM3U' in gap_text or '#EXTINF' in gap_text:
                                        gap_segments = process_m3u8(gap_text)
                                        
                                        # Add new segments
                                        for segment_url, segment_info in gap_segments.items():
                                            if segment_url not in seen_urls:
                                                seen_urls.add(segment_url)
                                                segments[segment_url] = segment_info
                                                segment_indices.add(segment_info['index'])
                                        
                                        print(f"[DEBUG] Gap position {gap_position}: Total segments now: {len(segments)}")
                                except Exception as gap_error:
                                    print(f"[DEBUG] Error on gap position {gap_position}: {str(gap_error)}")
                    else:
                        print("[DEBUG] Response doesn't appear to be an M3U8 playlist")
                    
                    time.sleep(delay)
                    
                    # If we have collected a significant number of segments, no need to retry
                    if len(segments) > 5:
                        break
                        
                except Exception as error:
                    print(f"[DEBUG] Error during attempt {attempt + 1} at position {position}: {str(error)}")
        
        # Check for gaps in segment indices
        if segment_indices:
            sorted_indices = sorted(list(segment_indices))
            if sorted_indices:
                min_index = sorted_indices[0]
                max_index = sorted_indices[-1]
                print(f"[DEBUG] Found segments with indices from {min_index} to {max_index}")
                
                # Return the segments
                return segments
        
        if not segments:
            print("[DEBUG] No segments found. The URL may be expired or invalid.")
        
        return segments
        
    except Exception as error:
        print(f"[DEBUG] Error in fetch_m3u8_segments: {str(error)}")
        return {}

def process_m3u8(response_text):
    lines = response_text.split('\n')
    print(f"[DEBUG] Found {len(lines)} lines in response")
    
    segments = {}
    current_duration = 0
    
    for i in range(len(lines)):
        line = lines[i].strip()
        
        if line.startswith('#EXTINF:'):
            # Parse duration
            duration_match = re.search(r'#EXTINF:([\d.]+)', line)
            current_duration = float(duration_match.group(1)) if duration_match else 0
            
            if i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                
                # Check if next line is a URL
                if next_line.startswith('http') or not next_line.startswith('#'):
                    segment_url = next_line
                    segment_index = extract_segment_index(segment_url)
                    segments[segment_url] = {
                        'duration': current_duration,
                        'index': segment_index
                    }
                    
                    print(f"[DEBUG] Added segment with index {segment_index}, duration: {current_duration}s")
    
    return segments

def extract_segment_index(url):
    # Try to extract from segment number in URL (e.g., _1_ts, _2_ts)
    seg_match = re.search(r'_(\d+)_ts', url)
    if seg_match:
        return int(seg_match.group(1))
    
    # Try to extract from range parameter
    range_match = re.search(r'range=(\d+)-', url)
    if range_match:
        return int(range_match.group(1))
    
    # Fallback to last number in URL
    last_number_match = re.search(r'(\d+)(?=[^0-9]*$)', url)
    if last_number_match:
        return int(last_number_match.group(1))
    
    # Default to a large number to avoid collisions
    return 2147483647  # Equivalent to Number.MAX_SAFE_INTEGER in JS

#--> Main
@app.route(rule='/')
def stream() -> Response:
    response: dict[str,str] = {
        'status'  : 'success',
        'service' : [
            {
                'method'   : 'GET',
                'endpoint' : 'get_config',
                'url'      : '{}get_config'.format(request.url_root),
                'params'   : [],
                'response' : ['status', 'mode']},
            {
                'method'   : 'POST',
                'endpoint' : 'generate_file',
                'url'      : '{}generate_file'.format(request.url_root),
                'params'   : ['mode', 'url'],
                'response' : ['status', 'js_token', 'browser_id', 'cookie', 'sign', 'timestamp', 'shareid', 'uk', 'list']},
            {
                'method'   : 'POST',
                'endpoint' : 'generate_link',
                'url'      : '{}generate_link'.format(request.url_root),
                'params'   : {
                    'mode1' : ['mode', 'js_token', 'cookie', 'sign', 'timestamp', 'shareid', 'uk', 'fs_id'],
                    'mode2' : ['mode', 'url']},
                'response' : ['status', 'download_link']}],
        'message' : 'hayo mau ngapain?'}
    return Response(response=json.dumps(obj=response, sort_keys=False), mimetype='application/json')

#--> Get Config App
@app.route('/get_config', methods=['GET'])
def getConfig() -> Response:
    global config
    try:
        x = TS()
        x.generateCookie()
        x.generateAuth()
        log = x.isLogin
        config = {'status':'success', **x.data} if log else {'status':'failed', 'message':'cookie terabox nya invalid bos, coba lapor ke dapunta', 'mode':1, 'cookie':''}
    except Exception as e:
        config = {'status':'failed', 'message':'i dont know why error in config.json : {}'.format(str(e)), 'mode':1, 'cookie':''}
    return Response(response=json.dumps(obj=config, sort_keys=False), mimetype='application/json')

#--> Get file
@app.route(rule='/generate_file', methods=['POST'])
def getFile() -> Response:
    global config
    try:
        data : dict = request.get_json()
        result = {'status':'failed', 'message':'invalid params'}
        mode = config.get('mode', 1)
        cookie = config.get('cookie','')
        if data.get('url') and mode:
            if mode == 1 or cookie == '': TF = TF1()
            elif mode == 2: TF = TF2(cookie)
            TF.search(data.get('url'))
            result = TF.result
    except Exception as e: result = {'status':'failed', 'message':'i dont know why error in terabox app : {}'.format(str(e))}
    return Response(response=json.dumps(obj=result, sort_keys=False), mimetype='application/json')

#--> Get link
@app.route(rule='/generate_link', methods=['POST'])
def getLink() -> Response:
    global config
    try:
        data : dict = request.get_json()
        result = {'status':'failed', 'message':'invalid params'}
        mode = config.get('mode', 1)
        if mode == 1:
            required_keys = {'fs_id', 'uk', 'shareid', 'timestamp', 'sign', 'js_token', 'cookie'}
            if all(key in data for key in required_keys):
                TL = TL1(**{key: data[key] for key in required_keys})
                TL.generate()
        elif mode == 2:
            required_keys = {'url'}
            if all(key in data for key in required_keys):
                TL = TL2(**{key: data[key] for key in required_keys})
            pass
        else : result = {'status':'failed', 'message':'gaada mode nya'}
        result = TL.result
    except: result = {'status':'failed', 'message':'wrong payload'}
    return Response(response=json.dumps(obj=result, sort_keys=False), mimetype='application/json')

#--> Get download
@app.route('/get_download', methods=['POST'])
def get_download():
    try:
        data = request.get_json()
        url = data.get('url')
        
        if not url:
            return Response(
                response=json.dumps({'status': 'failed', 'message': 'URL is required'}),
                mimetype='application/json'
            )

        print(f"[DEBUG] Processing URL: {url}")

        # Initialize TeraboxFile to get necessary tokens
        TF = TeraboxFile()
        TF.search(url)
        
        print(f"[DEBUG] TeraboxFile Result: {TF.result}")
        
        if TF.result['status'] != 'success':
            print(f"[DEBUG] Failed status in TF result")
            return Response(
                response=json.dumps({'status': 'failed', 'message': 'Could not fetch file info'}),
                mimetype='application/json'
            )

        files_data = []
        total_files = 0

        # Process all files in the list
        def process_files(file_list):
            nonlocal total_files
            processed_files = []
            print(f"[DEBUG] Processing file list: {file_list}")
            
            for file_item in file_list:
                # Convert is_dir to boolean properly
                is_dir = str(file_item['is_dir']) == '1'
                if is_dir:
                    print(f"[DEBUG] Found directory: {file_item['name']}")
                    processed_files.extend(process_files(file_item['list']))
                else:
                    print(f"[DEBUG] Processing file: {file_item['name']}")
                    total_files += 1
                    TL = TeraboxLink(
                        fs_id=file_item['fs_id'],
                        uk=TF.result['uk'],
                        shareid=TF.result['shareid'],
                        timestamp=TF.result['timestamp'],
                        sign=TF.result['sign'],
                        js_token=TF.result['js_token'],
                        cookie=TF.result['cookie']
                    )
                    TL.generate()
                    print(f"[DEBUG] TeraboxLink Result: {TL.result}")
                    
                    file_data = {
                        'name': file_item['name'],
                        'size': file_item['size'],
                        'type': file_item['type'],
                        'download_link': TL.result['download_link'],
                        'streaming_link': TL.result['streaming_link']
                    }
                    processed_files.append(file_data)
            
            return processed_files

        print(f"[DEBUG] Checking result keys: {TF.result.keys()}")

        # Check if it's a single file or a folder
        if 'fs_id' in TF.result:
            print("[DEBUG] Processing single file")
            # Handle single file case
            total_files = 1
            TL = TeraboxLink(
                fs_id=TF.result['fs_id'],
                uk=TF.result['uk'],
                shareid=TF.result['shareid'],
                timestamp=TF.result['timestamp'],
                sign=TF.result['sign'],
                js_token=TF.result['js_token'],
                cookie=TF.result['cookie']
            )
            TL.generate()
            print(f"[DEBUG] Single file TeraboxLink Result: {TL.result}")
            
            files_data = [{
                'name': TF.result.get('name', 'Unknown'),
                'size': TF.result.get('size', ''),
                'type': TF.result.get('type', 'other'),
                'download_link': TL.result['download_link'],
                'streaming_link': TL.result['streaming_link']
            }]
        elif TF.result.get('list'):
            print("[DEBUG] Processing folder")
            # Process all files starting from root
            files_data = process_files(TF.result['list'])
        else:
            print("[DEBUG] No file or folder information found")
            return Response(
                response=json.dumps({
                    'status': 'failed', 
                    'message': 'Could not find file or folder information',
                    'available_keys': list(TF.result.keys())
                }),
                mimetype='application/json'
            )

        print(f"[DEBUG] Final files_data: {files_data}")
        print(f"[DEBUG] Total files found: {total_files}")

        # Create response with all files' information
        response_data = {
            'status': 'success',
            'total_files': total_files,
            'files': files_data
        }

        return Response(
            response=json.dumps(response_data),
            mimetype='application/json'
        )

    except Exception as e:
        print(f"[DEBUG] Exception occurred: {str(e)}")
        import traceback
        print(f"[DEBUG] Traceback: {traceback.format_exc()}")
        return Response(
            response=json.dumps({
                'status': 'failed', 
                'message': f'Error processing request: {str(e)}',
                'traceback': traceback.format_exc()
            }),
            mimetype='application/json'
        )

#--> Get streaming links only
@app.route('/get_stream', methods=['POST'])
def get_stream():
    try:
        data = request.get_json()
        url = data.get('url')
        
        if not url:
            return Response(
                response=json.dumps({'status': 'failed', 'message': 'URL is required'}),
                mimetype='application/json'
            )

        print(f"[DEBUG] Processing URL for streaming: {url}")

        # Check URL format and validate before processing
        valid_domains = ['terafileshare.com', '1024tera.com', 'terabox.com', '1024terabox.com', 
                         'teraboxapp.com', 'dm.terabox.com', 'terasharelink.com']
        
        parsed_url = urlparse(url)
        is_valid_domain = any(domain in parsed_url.netloc for domain in valid_domains)
        
        if not is_valid_domain:
            return Response(
                response=json.dumps({
                    'status': 'failed', 
                    'message': 'Invalid TeraBox URL format or unsupported domain'
                }),
                mimetype='application/json'
            )
            
        # Handle short IDs (e.g., /s/1244) - could be invalid or malformed URLs
        if parsed_url.path.startswith('/s/') and len(parsed_url.path) < 15:
            path_parts = parsed_url.path.split('/')
            short_id = path_parts[-1] if len(path_parts) > 2 else ''
            
            if len(short_id) < 5:  # Usually TeraBox IDs are longer
                return Response(
                    response=json.dumps({
                        'status': 'failed', 
                        'message': 'Invalid or incomplete TeraBox link ID'
                    }),
                    mimetype='application/json'
                )

        # Initialize TeraboxFile to get necessary tokens
        TF = TeraboxFile()
        try:
            TF.search(url)
        except AttributeError as e:
            if "'NoneType' object has no attribute 'group'" in str(e):
                return Response(
                    response=json.dumps({
                        'status': 'failed', 
                        'message': 'URL format not recognized. Please use a standard TeraBox sharing link.'
                    }),
                    mimetype='application/json'
                )
            else:
                raise e
        
        print(f"[DEBUG] TeraboxFile Result: {TF.result}")
        
        if TF.result['status'] != 'success':
            return Response(
                response=json.dumps({'status': 'failed', 'message': 'Could not fetch file info'}),
                mimetype='application/json'
            )

        files_data = []
        total_files = 0

        # Process all files in the list
        def process_files(file_list):
            nonlocal total_files
            processed_files = []
            
            for file_item in file_list:
                # Convert is_dir to boolean properly
                is_dir = str(file_item['is_dir']) == '1'
                if is_dir:
                    processed_files.extend(process_files(file_item['list']))
                else:
                    # Check for video files - either explicitly marked or by extension
                    is_video = file_item.get('type') == 'video'
                    if not is_video and 'name' in file_item:
                        name = file_item['name'].lower()
                        video_extensions = ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.mpg', '.mpeg']
                        is_video = any(name.endswith(ext) for ext in video_extensions)
                    
                    if is_video:
                        total_files += 1
                        
                        # Use the TF object to get parameters that might change
                        TL = TeraboxLink(
                            fs_id=file_item['fs_id'],
                            uk=TF.result['uk'],
                            shareid=TF.result['shareid'],
                            timestamp=TF.result['timestamp'],
                            sign=TF.result['sign'],
                            js_token=TF.result['js_token'],
                            cookie=TF.result['cookie']
                        )

                        # Build streaming link with 1024tera.com format
                        params = {
                            'uk': TL.dynamic_params['uk'],
                            'shareid': TL.dynamic_params['shareid'],
                            'type': 'M3U8_FLV_264_480',
                            'fid': TL.dynamic_params['fid_list'].strip('[]'),
                            'sign': TL.dynamic_params['sign'],
                            'timestamp': TL.dynamic_params['timestamp'],
                            'jsToken': TL.dynamic_params['jsToken'],
                            'esl': '1',
                            'isplayer': '1',
                            'ehps': '1',
                            'clienttype': '0',
                            'app_id': '250528',
                            'web': '1',
                            'channel': 'dubox'
                        }

                        # Use the new URL format with 1024tera.com
                        streaming_link = 'https://www.1024tera.com/share/streaming?' + '&'.join([f'{a}={b}' for a,b in params.items()])
                        print(f"[DEBUG] Generated streaming link: {streaming_link}")
                        
                        # Fetch segments for this streaming link
                        segments = fetch_m3u8_segments(streaming_link)
                        
                        file_data = {
                            'name': file_item['name'],
                            'type': file_item['type'] if 'type' in file_item else 'video',
                            'streaming_link': streaming_link,
                            'segments': segments
                        }
                        processed_files.append(file_data)
            
            return processed_files

        # Check if it's a single file or a folder
        if 'fs_id' in TF.result:
            # Check if it's marked as video or try to determine by extension
            is_video = TF.result.get('type') == 'video'
            if not is_video and 'name' in TF.result:
                name = TF.result['name'].lower()
                video_extensions = ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.mpg', '.mpeg']
                is_video = any(name.endswith(ext) for ext in video_extensions)
                
            if is_video:
                total_files = 1
                
                # Use the TF object to get parameters that might change
                TL = TeraboxLink(
                    fs_id=TF.result['fs_id'],
                    uk=TF.result['uk'],
                    shareid=TF.result['shareid'],
                    timestamp=TF.result['timestamp'],
                    sign=TF.result['sign'],
                    js_token=TF.result['js_token'],
                    cookie=TF.result['cookie']
                )

                # Build streaming link with 1024tera.com format
                params = {
                    'uk': TL.dynamic_params['uk'],
                    'shareid': TL.dynamic_params['shareid'],
                    'type': 'M3U8_FLV_264_480',
                    'fid': TL.dynamic_params['fid_list'].strip('[]'),
                    'sign': TL.dynamic_params['sign'],
                    'timestamp': TL.dynamic_params['timestamp'],
                    'jsToken': TL.dynamic_params['jsToken'],
                    'esl': '1',
                    'isplayer': '1',
                    'ehps': '1',
                    'clienttype': '0',
                    'app_id': '250528',
                    'web': '1',
                    'channel': 'dubox'
                }

                # Use the new URL format with 1024tera.com
                streaming_link = 'https://www.1024tera.com/share/streaming?' + '&'.join([f'{a}={b}' for a,b in params.items()])
                print(f"[DEBUG] Generated streaming link for single file: {streaming_link}")
                
                # Fetch segments for this streaming link
                segments = fetch_m3u8_segments(streaming_link)
                
                files_data = [{
                    'name': TF.result.get('name', 'Unknown'),
                    'type': TF.result.get('type', 'video'),
                    'streaming_link': streaming_link,
                    'segments': segments
                }]
            else:
                # Try as video anyway (sometimes files aren't properly marked)
                try:
                    TL = TeraboxLink(
                        fs_id=TF.result['fs_id'],
                        uk=TF.result['uk'],
                        shareid=TF.result['shareid'],
                        timestamp=TF.result['timestamp'],
                        sign=TF.result['sign'],
                        js_token=TF.result['js_token'],
                        cookie=TF.result['cookie']
                    )

                    # Build streaming link with 1024tera.com format
                    params = {
                        'uk': TL.dynamic_params['uk'],
                        'shareid': TL.dynamic_params['shareid'],
                        'type': 'M3U8_FLV_264_480',
                        'fid': TL.dynamic_params['fid_list'].strip('[]'),
                        'sign': TL.dynamic_params['sign'],
                        'timestamp': TL.dynamic_params['timestamp'],
                        'jsToken': TL.dynamic_params['jsToken'],
                        'esl': '1',
                        'isplayer': '1',
                        'ehps': '1',
                        'clienttype': '0',
                        'app_id': '250528',
                        'web': '1',
                        'channel': 'dubox'
                    }

                    streaming_link = 'https://www.1024tera.com/share/streaming?' + '&'.join([f'{a}={b}' for a,b in params.items()])
                    segments = fetch_m3u8_segments(streaming_link)
                    
                    if segments:
                        total_files = 1
                        files_data = [{
                            'name': TF.result.get('name', 'Unknown'),
                            'type': 'video',  # Force type as video since we got segments
                            'streaming_link': streaming_link,
                            'segments': segments
                        }]
                    else:
                        return Response(
                            response=json.dumps({
                                'status': 'failed', 
                                'message': 'The file is not a video and cannot be streamed'
                            }),
                            mimetype='application/json'
                        )
                except Exception as e:
                    return Response(
                        response=json.dumps({
                            'status': 'failed', 
                            'message': f'The file is not a video and cannot be streamed: {str(e)}'
                        }),
                        mimetype='application/json'
                    )
        elif TF.result.get('list'):
            # Process all files starting from root
            files_data = process_files(TF.result['list'])
        else:
            return Response(
                response=json.dumps({
                    'status': 'failed', 
                    'message': 'Could not find file or folder information'
                }),
                mimetype='application/json'
            )

        if not files_data or total_files == 0:
            return Response(
                response=json.dumps({
                    'status': 'failed', 
                    'message': 'No video files found that can be streamed'
                }),
                mimetype='application/json'
            )

        # Create response with streaming links only
        response_data = {
            'status': 'success',
            'total_files': total_files,
            'files': files_data
        }

        return Response(
            response=json.dumps(response_data),
            mimetype='application/json'
        )

    except Exception as e:
        import traceback
        print(f"[DEBUG] Exception occurred: {str(e)}")
        print(f"[DEBUG] Traceback: {traceback.format_exc()}")
        return Response(
            response=json.dumps({
                'status': 'failed', 
                'message': f'Error processing streaming request: {str(e)}'
            }),
            mimetype='application/json'
        )

#--> Get streaming via TeraBox's direct API method
@app.route('/get_direct_stream', methods=['POST'])
def get_direct_stream():
    try:
        data = request.get_json()
        url = data.get('url')
        
        if not url:
            return Response(
                response=json.dumps({'status': 'failed', 'message': 'URL is required'}),
                mimetype='application/json'
            )

        print(f"[DEBUG] Processing URL for direct streaming: {url}")

        # Initialize TeraboxFile to get necessary file info
        TF = TeraboxFile()
        TF.search(url)
        
        if TF.result['status'] != 'success':
            return Response(
                response=json.dumps({'status': 'failed', 'message': 'Could not fetch file info'}),
                mimetype='application/json'
            )

        files_data = []
        total_files = 0

        # Process all files in the list
        def process_files(file_list):
            nonlocal total_files
            processed_files = []
            
            for file_item in file_list:
                # Convert is_dir to boolean properly
                is_dir = str(file_item['is_dir']) == '1'
                if is_dir:
                    processed_files.extend(process_files(file_item['list']))
                else:
                    # Only process video files for streaming
                    if file_item['type'] == 'video':
                        total_files += 1
                        
                        # Get file path from file_item
                        file_path = file_item['path']
                        
                        # URL encode the path
                        encoded_path = urllib.parse.quote(file_path)
                        
                        # Generate direct streaming URL using the API endpoint
                        direct_api_url = f"https://www.1024terabox.com/api/streaming?path={encoded_path}&app_id=250528&clienttype=0&type=M3U8_FLV_264_480&vip=0"
                        
                        # Generate fallback streaming URL
                        params = {
                            'uk': TF.result['uk'],
                            'shareid': TF.result['shareid'],
                            'type': 'M3U8_FLV_264_480',
                            'fid': file_item['fs_id'],
                            'sign': TF.result['sign'],
                            'timestamp': TF.result['timestamp'],
                            'jsToken': TF.result['js_token'],
                            'esl': '1',
                            'isplayer': '1',
                            'ehps': '1',
                            'clienttype': '0',
                            'app_id': '250528',
                            'web': '1',
                            'channel': 'dubox'
                        }
                        fallback_url = 'https://www.1024tera.com/share/streaming?' + '&'.join([f'{a}={b}' for a,b in params.items()])
                        
                        # Get TeraboxLink for direct download option too
                        TL = TeraboxLink(
                            fs_id=file_item['fs_id'],
                            uk=TF.result['uk'],
                            shareid=TF.result['shareid'],
                            timestamp=TF.result['timestamp'],
                            sign=TF.result['sign'],
                            js_token=TF.result['js_token'],
                            cookie=TF.result['cookie']
                        )
                        TL.generate()
                        
                        # Get download URL if available
                        download_url = ""
                        if TL.result['status'] == 'success' and TL.result.get('download_link'):
                            if isinstance(TL.result['download_link'], dict):
                                for key in ['url_3', 'url_2', 'url_1']:
                                    if key in TL.result['download_link']:
                                        download_url = TL.result['download_link'][key]
                                        break
                        
                        file_data = {
                            'name': file_item['name'],
                            'type': file_item['type'],
                            'direct_streaming_url': direct_api_url,
                            'fallback_streaming_url': fallback_url,
                            'download_url': download_url,
                            'path': file_path,
                            'note': 'The direct_streaming_url requires user authentication cookies'
                        }
                        processed_files.append(file_data)
            
            return processed_files

        # Check if it's a single file or a folder
        if 'fs_id' in TF.result:
            # Handle single file case
            if TF.result.get('type') == 'video':
                total_files = 1
                
                # Get file path - we might need to construct it
                file_path = TF.result.get('path', f"/{TF.result.get('name', 'video.mp4')}")
                
                # URL encode the path
                encoded_path = urllib.parse.quote(file_path)
                
                # Generate direct streaming URL using the API endpoint
                direct_api_url = f"https://www.1024terabox.com/api/streaming?path={encoded_path}&app_id=250528&clienttype=0&type=M3U8_FLV_264_480&vip=0"
                
                # Generate fallback streaming URL
                params = {
                    'uk': TF.result['uk'],
                    'shareid': TF.result['shareid'],
                    'type': 'M3U8_FLV_264_480',
                    'fid': TF.result['fs_id'],
                    'sign': TF.result['sign'],
                    'timestamp': TF.result['timestamp'],
                    'jsToken': TF.result['js_token'],
                    'esl': '1',
                    'isplayer': '1',
                    'ehps': '1',
                    'clienttype': '0',
                    'app_id': '250528',
                    'web': '1',
                    'channel': 'dubox'
                }
                fallback_url = 'https://www.1024tera.com/share/streaming?' + '&'.join([f'{a}={b}' for a,b in params.items()])
                
                # Get TeraboxLink for direct download option too
                TL = TeraboxLink(
                    fs_id=TF.result['fs_id'],
                    uk=TF.result['uk'],
                    shareid=TF.result['shareid'],
                    timestamp=TF.result['timestamp'],
                    sign=TF.result['sign'],
                    js_token=TF.result['js_token'],
                    cookie=TF.result['cookie']
                )
                TL.generate()
                
                # Get download URL if available
                download_url = ""
                if TL.result['status'] == 'success' and TL.result.get('download_link'):
                    if isinstance(TL.result['download_link'], dict):
                        for key in ['url_3', 'url_2', 'url_1']:
                            if key in TL.result['download_link']:
                                download_url = TL.result['download_link'][key]
                                break
                
                files_data = [{
                    'name': TF.result.get('name', 'Unknown'),
                    'type': TF.result.get('type', 'video'),
                    'direct_streaming_url': direct_api_url,
                    'fallback_streaming_url': fallback_url,
                    'download_url': download_url,
                    'path': file_path,
                    'note': 'The direct_streaming_url requires user authentication cookies'
                }]
            else:
                return Response(
                    response=json.dumps({
                        'status': 'failed', 
                        'message': 'The file is not a video and cannot be streamed'
                    }),
                    mimetype='application/json'
                )
        elif TF.result.get('list'):
            # Process all files starting from root
            files_data = process_files(TF.result['list'])
        else:
            return Response(
                response=json.dumps({
                    'status': 'failed', 
                    'message': 'Could not find file or folder information'
                }),
                mimetype='application/json'
            )

        # Create response with all streaming options
        response_data = {
            'status': 'success',
            'total_files': total_files,
            'files': files_data,
            'instructions': 'To use the direct_streaming_url, you need to be logged in to TeraBox and include your TeraBox cookies in the request.'
        }

        return Response(
            response=json.dumps(response_data),
            mimetype='application/json'
        )

    except Exception as e:
        import traceback
        print(f"[DEBUG] Exception occurred: {str(e)}")
        print(f"[DEBUG] Traceback: {traceback.format_exc()}")
        return Response(
            response=json.dumps({
                'status': 'failed', 
                'message': f'Error processing streaming request: {str(e)}'
            }),
            mimetype='application/json'
        )

@app.route('/proxy_stream', methods=['GET', 'OPTIONS'])
def proxy_stream():
    # Handle origin for file:// protocol
    origin = request.headers.get('Origin', 'http://localhost')
    if origin == 'null' or not origin.startswith(('http://', 'https://')):
        origin = 'http://localhost'

    if request.method == 'OPTIONS':
        response = Response()
        response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = '*'
        response.headers['Access-Control-Allow-Credentials'] = 'true'
        response.headers['Vary'] = 'Origin'
        return response

    try:
        path = request.args.get('path')
        url = request.args.get('url')
        
        if path:
            # Direct path-based API request
            decoded_path = urllib.parse.unquote(path)
            api_url = f"https://www.1024terabox.com/api/streaming?path={decoded_path}&app_id=250528&clienttype=0&type=M3U8_FLV_264_480&vip=0"
        elif url:
            # Already formatted URL
            api_url = urllib.parse.unquote(url)
        
        # Get origin from request headers
        origin = request.headers.get('Origin', '*')
        
        # Improved headers with CORS validation
        headers = {
            'Referer': 'https://www.1024terabox.com/',
            'Origin': 'https://www.1024terabox.com',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Cookie': '; '.join([f'{k}={v}' for k,v in request.cookies.items()]),
        }

        # Add security headers
        response_headers = {
            'Access-Control-Allow-Origin': origin,
            'Access-Control-Allow-Credentials': 'true',
            'Access-Control-Expose-Headers': 'Content-Length,Content-Range',
            'Vary': 'Origin',
            'Content-Security-Policy': "default-src 'self' https://*.1024terabox.com"
        }

        # Decode URL only once
        final_url = urllib.parse.unquote(api_url)
        
        # Improved HLS detection
        is_hls = 'm3u8' in final_url.lower() or 'type=M3U8' in final_url.upper()
        
        try:
            # Add timeout to prevent hanging requests
            resp = requests.get(
                final_url,
                headers=headers,
                cookies=request.cookies,
                stream=True,
                verify=False,
                timeout=(3.05, 30),
                allow_redirects=True  # Handle redirects properly
            )
        except requests.exceptions.Timeout:
            return jsonify({'error': 'Upstream timeout'}), 504

        # Validate response before processing
        if resp.status_code != 200:
            return jsonify({'error': f'Upstream error: {resp.status_code}'}), resp.status_code

        # Detect HLS content more accurately
        content_type = resp.headers.get('Content-Type', '')
        is_hls = is_hls or 'mpegurl' in content_type.lower() or 'application/vnd.apple.mpegurl' in content_type.lower()

        # Process HLS manifest
        if is_hls:
            manifest = resp.content.decode('utf-8')
            # Fix relative paths and segment URLs
            manifest = re.sub(
                r'(.*?\.ts)',
                lambda m: f'/proxy_stream?url={urllib.parse.quote(urllib.parse.urljoin(final_url, m.group(0)))}',
                manifest
            )
            response_headers['Content-Type'] = 'application/vnd.apple.mpegurl'
            return Response(manifest, headers=response_headers)

        # Forward headers with proper content type
        response_headers['Content-Type'] = content_type
        response_headers['Content-Length'] = resp.headers.get('Content-Length', '')
        response_headers['Content-Range'] = resp.headers.get('Content-Range', '')
        response_headers['Accept-Ranges'] = 'bytes'

        # Add critical CORS headers to all responses
        if is_hls:
            response_headers['Content-Type'] = 'application/vnd.apple.mpegurl'
        else:
            response_headers['Content-Type'] = resp.headers.get('Content-Type', 'video/mp4')

        # Add this after getting the final_url
        if '1024tera.com' in final_url:
            headers['Origin'] = 'https://www.1024tera.com'
            headers['Referer'] = 'https://www.1024tera.com/'
        
        # Add security headers to response
        response_headers.update({
            'Access-Control-Allow-Origin': origin,
            'Access-Control-Expose-Headers': 'Content-Length,Content-Range',
            'Access-Control-Allow-Credentials': 'true'
        })

        # Add these headers for HLS compatibility
        response_headers.update({
            'Accept-Ranges': 'bytes',
            'Connection': 'keep-alive',
            'Transfer-Encoding': 'chunked',
            'Cache-Control': 'no-cache, no-store, must-revalidate',
            'Pragma': 'no-cache',
            'Expires': '0'
        })

        # Create final response with security headers
        response = Response(
            resp.iter_content(chunk_size=1024*1024),
            headers=response_headers,
            status=resp.status_code
        )
        return response
    except Exception as e:
        print(f"Proxy error: {str(e)}")
        return jsonify({'error': str(e)}), 500

# Add a new function to generate M3U8 playlist from segments
def generate_m3u8_playlist(segments, quick_start=True):
    # Sort segments by index
    sorted_segments = sorted(segments.items(), key=lambda x: x[1]['index'])
    
    # Calculate target duration (ceiling of max segment duration)
    max_duration = max([info['duration'] for _, info in sorted_segments], default=10)
    target_duration = math.ceil(max_duration)
    
    # Create playlist lines
    playlist_lines = [
        '#EXTM3U',
        '#EXT-X-VERSION:3',
        f'#EXT-X-TARGETDURATION:{target_duration}',
        '#EXT-X-MEDIA-SEQUENCE:0',
        '#EXT-X-PLAYLIST-TYPE:VOD'
    ]
    
    # Add segments
    for url, info in sorted_segments:
        duration = info['duration']
        playlist_lines.append(f'#EXTINF:{duration:.3f},')
        playlist_lines.append(url)
    
    # Add end marker
    playlist_lines.append('#EXT-X-ENDLIST')
    
    return '\n'.join(playlist_lines)

#--> Get streaming links as playable M3U8
@app.route('/play_stream', methods=['GET'])
def play_stream():
    try:
        url = request.args.get('url')
        # Get index parameter if provided (for folders with multiple files)
        file_index = request.args.get('index')
        if file_index:
            try:
                file_index = int(file_index)
            except ValueError:
                return Response(
                    response=json.dumps({'status': 'failed', 'message': 'Index parameter must be a number'}),
                    mimetype='application/json'
                )
        
        if not url:
            return Response(
                response=json.dumps({'status': 'failed', 'message': 'URL is required'}),
                mimetype='application/json'
            )

        print(f"[DEBUG] Processing URL for direct playback streaming: {url}")

        # Initialize TeraboxFile to get necessary tokens
        TF = TeraboxFile()
        TF.search(url)
        
        print(f"[DEBUG] TeraboxFile result status: {TF.result.get('status')}")
        print(f"[DEBUG] TeraboxFile result keys: {list(TF.result.keys())}")
        
        if TF.result['status'] != 'success':
            return Response(
                response=json.dumps({'status': 'failed', 'message': 'Could not fetch file info'}),
                mimetype='application/json'
            )

        # Check if it's a single file
        if 'fs_id' in TF.result:
            print(f"[DEBUG] Single file detected with type: {TF.result.get('type')}")
            if TF.result.get('type') == 'video':
                # Use the TF object to get parameters that might change
                TL = TeraboxLink(
                    fs_id=TF.result['fs_id'],
                    uk=TF.result['uk'],
                    shareid=TF.result['shareid'],
                    timestamp=TF.result['timestamp'],
                    sign=TF.result['sign'],
                    js_token=TF.result['js_token'],
                    cookie=TF.result['cookie']
                )
                
                print(f"[DEBUG] Generated TeraboxLink with dynamic params: {TL.dynamic_params}")

                # Build streaming link with 1024tera.com format
                params = {
                    'uk': TL.dynamic_params['uk'],
                    'shareid': TL.dynamic_params['shareid'],
                    'type': 'M3U8_FLV_264_480',
                    'fid': TL.dynamic_params['fid_list'].strip('[]'),
                    'sign': TL.dynamic_params['sign'],
                    'timestamp': TL.dynamic_params['timestamp'],
                    'jsToken': TL.dynamic_params['jsToken'],
                    'esl': '1',
                    'isplayer': '1',
                    'ehps': '1',
                    'clienttype': '0',
                    'app_id': '250528',
                    'web': '1',
                    'channel': 'dubox'
                }

                # Use the new URL format with 1024tera.com
                streaming_link = 'https://www.1024tera.com/share/streaming?' + '&'.join([f'{a}={b}' for a,b in params.items()])
                print(f"[DEBUG] Generated streaming link for playback: {streaming_link}")
                
                # Fetch segments for this streaming link
                segments = fetch_m3u8_segments(streaming_link)
                print(f"[DEBUG] Fetched {len(segments)} segments for the video")
                
                if segments:
                    # Generate a playable M3U8 playlist
                    playlist = generate_m3u8_playlist(segments)
                    
                    # Return the playlist with appropriate headers
                    response = Response(
                        response=playlist,
                        mimetype='application/vnd.apple.mpegurl'
                    )
                    
                    # Add headers for better playback compatibility
                    response.headers['Content-Disposition'] = f'attachment; filename="{TF.result.get("name", "video")}.m3u8"'
                    return response
                else:
                    return Response(
                        response=json.dumps({
                            'status': 'failed', 
                            'message': 'Could not fetch any segments for the video'
                        }),
                        mimetype='application/json'
                    )
            else:
                # Try to treat it as video even if the type isn't explicitly 'video'
                try:
                    print(f"[DEBUG] Attempting to treat as video even though type is {TF.result.get('type')}")
                    # Use the TF object to get parameters that might change
                    TL = TeraboxLink(
                        fs_id=TF.result['fs_id'],
                        uk=TF.result['uk'],
                        shareid=TF.result['shareid'],
                        timestamp=TF.result['timestamp'],
                        sign=TF.result['sign'],
                        js_token=TF.result['js_token'],
                        cookie=TF.result['cookie']
                    )
                    
                    print(f"[DEBUG] Generated TeraboxLink with dynamic params: {TL.dynamic_params}")

                    # Build streaming link with 1024tera.com format
                    params = {
                        'uk': TL.dynamic_params['uk'],
                        'shareid': TL.dynamic_params['shareid'],
                        'type': 'M3U8_FLV_264_480',
                        'fid': TL.dynamic_params['fid_list'].strip('[]'),
                        'sign': TL.dynamic_params['sign'],
                        'timestamp': TL.dynamic_params['timestamp'],
                        'jsToken': TL.dynamic_params['jsToken'],
                        'esl': '1',
                        'isplayer': '1',
                        'ehps': '1',
                        'clienttype': '0',
                        'app_id': '250528',
                        'web': '1',
                        'channel': 'dubox'
                    }

                    # Use the new URL format with 1024tera.com
                    streaming_link = 'https://www.1024tera.com/share/streaming?' + '&'.join([f'{a}={b}' for a,b in params.items()])
                    print(f"[DEBUG] Generated streaming link for playback attempt: {streaming_link}")
                    
                    # Fetch segments for this streaming link
                    segments = fetch_m3u8_segments(streaming_link)
                    print(f"[DEBUG] Fetched {len(segments)} segments for the attempted video")
                    
                    if segments:
                        # Generate a playable M3U8 playlist
                        playlist = generate_m3u8_playlist(segments)
                        
                        # Return the playlist with appropriate headers
                        response = Response(
                            response=playlist,
                            mimetype='application/vnd.apple.mpegurl'
                        )
                        
                        # Add headers for better playback compatibility
                        response.headers['Content-Disposition'] = f'attachment; filename="{TF.result.get("name", "video")}.m3u8"'
                        return response
                    else:
                        raise Exception("No segments found in attempt")
                except Exception as e:
                    print(f"[DEBUG] Attempt to treat as video failed: {str(e)}")
                    return Response(
                        response=json.dumps({
                            'status': 'failed', 
                            'message': f'The file is not a video and cannot be streamed. Type: {TF.result.get("type", "unknown")}'
                        }),
                        mimetype='application/json'
                    )
        elif TF.result.get('list'):
            print(f"[DEBUG] Folder detected with {len(TF.result['list'])} items")
            # It's a folder - find all video files
            video_files = []
            
            def process_files(file_list):
                nonlocal video_files
                for file_item in file_list:
                    # Convert is_dir to boolean properly
                    is_dir = str(file_item['is_dir']) == '1'
                    if is_dir:
                        process_files(file_item['list'])
                    else:
                        # Accept both 'video' type and items without type but with video extensions
                        is_video = file_item.get('type') == 'video'
                        if not is_video and 'name' in file_item:
                            name = file_item['name'].lower()
                            video_extensions = ['.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.mpg', '.mpeg']
                            is_video = any(name.endswith(ext) for ext in video_extensions)
                        
                        if is_video:
                            video_files.append(file_item)
            
            # Process all files to find videos
            process_files(TF.result['list'])
            print(f"[DEBUG] Found {len(video_files)} video files in folder")
            
            if not video_files:
                return Response(
                    response=json.dumps({
                        'status': 'failed', 
                        'message': 'No video files found in the folder'
                    }),
                    mimetype='application/json'
                )
            
            # Auto-play if there's only one video file and no specific index requested
            if len(video_files) == 1 and file_index is None:
                print(f"[DEBUG] Auto-playing the only video file found")
                file_index = 0
            
            # If no index provided, return a list of available videos
            if file_index is None:
                videos_list = []
                for i, file in enumerate(video_files):
                    videos_list.append({
                        'index': i,
                        'name': file['name'],
                        'size': file.get('size', 'Unknown'),
                        'playback_url': f"{request.url_root.rstrip('/')}/play_stream?url={urllib.parse.quote(url)}&index={i}"
                    })
                
                return Response(
                    response=json.dumps({
                        'status': 'success',
                        'message': 'Please select a video to play by adding &index=N to the URL',
                        'videos': videos_list
                    }),
                    mimetype='application/json'
                )
            
            # Check if the index is valid
            if file_index < 0 or file_index >= len(video_files):
                return Response(
                    response=json.dumps({
                        'status': 'failed', 
                        'message': f'Invalid index. Choose from 0 to {len(video_files)-1}',
                        'total_videos': len(video_files)
                    }),
                    mimetype='application/json'
                )
            
            # Get the selected video file
            selected_file = video_files[file_index]
            print(f"[DEBUG] Selected video file: {selected_file['name']}")
            
            # Use the TF object to get parameters that might change
            TL = TeraboxLink(
                fs_id=selected_file['fs_id'],
                uk=TF.result['uk'],
                shareid=TF.result['shareid'],
                timestamp=TF.result['timestamp'],
                sign=TF.result['sign'],
                js_token=TF.result['js_token'],
                cookie=TF.result['cookie']
            )
            
            print(f"[DEBUG] Generated TeraboxLink for folder video with dynamic params: {TL.dynamic_params}")

            # Build streaming link with 1024tera.com format
            params = {
                'uk': TL.dynamic_params['uk'],
                'shareid': TL.dynamic_params['shareid'],
                'type': 'M3U8_FLV_264_480',
                'fid': TL.dynamic_params['fid_list'].strip('[]'),
                'sign': TL.dynamic_params['sign'],
                'timestamp': TL.dynamic_params['timestamp'],
                'jsToken': TL.dynamic_params['jsToken'],
                'esl': '1',
                'isplayer': '1',
                'ehps': '1',
                'clienttype': '0',
                'app_id': '250528',
                'web': '1',
                'channel': 'dubox'
            }

            # Use the new URL format with 1024tera.com
            streaming_link = 'https://www.1024tera.com/share/streaming?' + '&'.join([f'{a}={b}' for a,b in params.items()])
            print(f"[DEBUG] Generated streaming link for selected video: {streaming_link}")
            
            # Fetch segments for this streaming link
            segments = fetch_m3u8_segments(streaming_link)
            print(f"[DEBUG] Fetched {len(segments)} segments for the selected video")
            
            if segments:
                # Generate a playable M3U8 playlist
                playlist = generate_m3u8_playlist(segments)
                
                # Return the playlist with appropriate headers
                response = Response(
                    response=playlist,
                    mimetype='application/vnd.apple.mpegurl'
                )
                
                # Add headers for better playback compatibility
                response.headers['Content-Disposition'] = f'attachment; filename="{selected_file.get("name", "video")}.m3u8"'
                return response
            else:
                return Response(
                    response=json.dumps({
                        'status': 'failed', 
                        'message': 'Could not fetch any segments for the selected video'
                    }),
                    mimetype='application/json'
                )
        else:
            print(f"[DEBUG] Neither single file nor folder detected. Result keys: {list(TF.result.keys())}")
            return Response(
                response=json.dumps({
                    'status': 'failed', 
                    'message': 'Could not find file or folder information'
                }),
                mimetype='application/json'
            )

    except Exception as e:
        import traceback
        print(f"[DEBUG] Exception occurred: {str(e)}")
        print(f"[DEBUG] Traceback: {traceback.format_exc()}")
        return Response(
            response=json.dumps({
                'status': 'failed', 
                'message': f'Error processing playback request: {str(e)}'
            }),
            mimetype='application/json'
        )

#--> Initialization
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

# https://1024terabox.com/s/1eBHBOzcEI-VpUGA_xIcGQg
# https://dm.terabox.com/indonesian/sharing/link?surl=KKG3LQ7jaT733og97CBcGg
# https://terasharelink.com/s/1QHHiN_C2wyDbckF_V3ssIw
