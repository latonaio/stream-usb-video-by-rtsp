# 概要
接続されたUSBカメラから画像データ取得し、RTSP方式で他マイクロサービスに画像データを配信するサービスです。

# 動作環境
このマイクロサービスはAIONのプラットフォーム上での動作を前提としています。 使用する際は、事前にAIONの動作環境を用意してください。AIONに関しては[こちら](https://github.com/latonaio/aion-core)をご覧ください。

- OS: Linux

- CPU: Intel64/AMD64/ARM64

- Kubernetes

- AION

# カメラ設定
下記のpathに配置してある設定ファイルを読み込んで、auto_focusなどの設定を行います。

`/var/lib/aion/Data/stream-usb-video-by-rtsp_{MS_NUMBER}/config.json`

現状では各設定はデフォルトで
```
auto_focus：True
focus_absolute: 50
```
に設定されています。(変更不可)

# I/O
kanbanのmeta dataから下記のデータを入出力します。
### input
device_list: 接続されているデバイスのリストです。check-multiple-camera-connection-kubeサービスで生成されます。
auto_focus: オートフォーカスの設定です

### output
- width: 解像度横幅 
- height: 解像度縦幅 
- framerate: 秒間フレームレート
- addr:rtspで通信するためのuri。`rtsp://{SERVICE_NAME}-{MS_NUMBER}-srv:{ポート番号}`の形式になります。

※ ポート番号は、環境変数で指定したデフォルトの番号に、全登録デバイスの中のそのデバイスの登録順を加えたものが割り振られます。

※ docker環境では一律`localhost:{port}`に指定されます。


## 環境変数
- WIDTH(解像度横幅,default: 864)
- HEIGHT(解像度縦幅,default: 480)
- FPSI(フレームレート,default: 10)
- PORT(TSP通信ポート,default: 8554)
- URI(RTSP通信アドレス,default:"/usb")
- MS_NUMBER(aion-core全体の変数. 値はproject.yamlを参照してください)