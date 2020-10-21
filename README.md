# What is this?
USBカメラから画像データ取得して、RTSPストリーミングするサービスです。

## Notes
- 画像ストリーミング情報を出力　metadta 
```
{
    "width": width,
    "height": height,
    "framerate": fps,
    "addr": uri,
}
```

## 環境変数
- WIDTH&emsp;解像度横幅 (default: 864)
- HEIGHT&emsp;解像度縦幅 (default: 480)
- FPS&emsp;１秒間に取得する画像数Frames Per Second (default: 10)
- PORT&emsp;RTSP通信ポート (default: 8554)
- URI&emsp;RTSP通信アドレス (default:"/usb")
