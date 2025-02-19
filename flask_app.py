#--> Standard module & library
import json

#--> Flask
from flask import Flask, Response, request
from flask_cors import CORS
app = Flask(import_name=__name__)
CORS(app=app)

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

#--> Initialization
if __name__ == '__main__':
    app.run(debug=True)

# https://1024terabox.com/s/1eBHBOzcEI-VpUGA_xIcGQg
# https://dm.terabox.com/indonesian/sharing/link?surl=KKG3LQ7jaT733og97CBcGg
# https://terasharelink.com/s/1QHHiN_C2wyDbckF_V3ssIw
