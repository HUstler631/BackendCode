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

        # Initialize TeraboxFile to get necessary tokens
        TF = TeraboxFile()
        TF.search(url)
        
        if TF.result['status'] != 'success':
            return Response(
                response=json.dumps({'status': 'failed', 'message': 'Could not fetch file info'}),
                mimetype='application/json'
            )

        # Get first file's info
        first_file = TF.result['list'][0]
        fs_id = first_file['fs_id']
        
        # Initialize TeraboxLink to get download and streaming URLs
        TL = TeraboxLink(
            fs_id=fs_id,
            uk=TF.result['uk'],
            shareid=TF.result['shareid'],
            timestamp=TF.result['timestamp'],
            sign=TF.result['sign'],
            js_token=TF.result['js_token'],
            cookie=TF.result['cookie']
        )
        TL.generate()

        # Create response with both download and streaming links
        response_data = {
            'status': TL.result['status'],
            'download_link': TL.result['download_link'],
            'streaming_link': TL.result['streaming_link'],
            'file_info': {
                'name': first_file['name'],
                'size': first_file['size'],
                'type': first_file['type']
            }
        }

        return Response(
            response=json.dumps(response_data),
            mimetype='application/json'
        )

    except Exception as e:
        return Response(
            response=json.dumps({'status': 'failed', 'message': str(e)}),
            mimetype='application/json'
        )

#--> Initialization
if __name__ == '__main__':
    app.run(debug=True)

# https://1024terabox.com/s/1eBHBOzcEI-VpUGA_xIcGQg
# https://dm.terabox.com/indonesian/sharing/link?surl=KKG3LQ7jaT733og97CBcGg
# https://terasharelink.com/s/1QHHiN_C2wyDbckF_V3ssIw