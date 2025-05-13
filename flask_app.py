#--> Standard module & library
import json
import requests
import urllib.parse
import re
import os

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

        # Initialize TeraboxFile to get necessary tokens
        TF = TeraboxFile()
        TF.search(url)
        
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
                    # Only process video files for streaming
                    if file_item['type'] == 'video':
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
                        
                        file_data = {
                            'name': file_item['name'],
                            'type': file_item['type'],
                            'streaming_link': streaming_link
                        }
                        processed_files.append(file_data)
            
            return processed_files

        # Check if it's a single file or a folder
        if 'fs_id' in TF.result:
            # Handle single file case
            if TF.result.get('type') == 'video':
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
                
                files_data = [{
                    'name': TF.result.get('name', 'Unknown'),
                    'type': TF.result.get('type', 'other'),
                    'streaming_link': streaming_link
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

#--> Initialization
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

# https://1024terabox.com/s/1eBHBOzcEI-VpUGA_xIcGQg
# https://dm.terabox.com/indonesian/sharing/link?surl=KKG3LQ7jaT733og97CBcGg
# https://terasharelink.com/s/1QHHiN_C2wyDbckF_V3ssIw
