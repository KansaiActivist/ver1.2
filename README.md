にょん姉貴が登場☆ v1.2

Python製のデスクトップマスコットです。PySide6を使用し、アニメーション、音声再生、設定変更に対応しています。Python 3.14で動作確認済みです。

## 起動

プロジェクト直下で実行してください。

```bash
python main.py
```

## 素材

画像・音声素材は `assets/` に同梱されています。画像は `assets/<状態名>/`、音声は `assets/voices/<イベント名>/` に配置されており、自由に差し替えられます。素材がない場合は、簡易キャラクターが表示されます。素材がない場合は、簡易的なキャラクターが生成されます。

## EXE化

PySide6を使用しています。`main.py` が起動ファイルで、EXE化する場合のエントリポイントです。
"python -m PyInstaller --noconsole --noconfirm main.py"でコンパイルしてください。
アイコンを設定したい場合
"python -m PyInstaller --noconsole --noconfirm --icon=アイコンのファイル名.ico main.py"でコンパイルしてください。

## OS対応について

Windowsでは他のアプリのウィンドウ上を歩く機能を実装しています。macOSとLinux X11にも同機能の実装がありますが、いずれも実機ではテストしていません。Windowsを含め、OSのウィンドウ取得処理は実機未検証です。Linux WaylandではOSの仕様により他アプリのウィンドウ上を歩く機能は使えず、画面下端のみ歩きます。

