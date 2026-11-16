# アーキテクチャ(デスクトップマスコット)

起動: `python main.py`(または `python -m mascot`)。素材は `main.py` と同じ場所の `assets/` に置く(従来どおり)。
exe化する場合のエントリは `main.py`。

## 構成と責務

```
main.py                      起動スクリプト(mascot.app.run を呼ぶだけ)
mascot/
  config.py                  設定・パス・定数・設定ファイルの読み書き      ← 最下層。何にも依存しない
  diagnostics.py             ログ設定
  system/                    OS依存の処理(OSごとの分岐はここに閉じ込める)
    memory.py                  メモリ使用量・未使用領域の返却
    window_api.py              【他アプリのウィンドウ取得】取得口の契約(型・理由文)
    window_factory.py          このOSで使える取得口を選ぶ(Wayland等は理由つきで無効)
    window_win32.py            Windows 実装(ctypes。追加ライブラリ不要)
    window_macos.py            macOS 実装(任意: pyobjc-framework-Quartz)
    window_x11.py              Linux X11 実装(任意: python-xlib)
  surfaces/                  【ウィンドウ上の足場】Qt にも OS にも依存しない
    geometry.py                長方形・画面情報・座標変換・足場(上端の区間)の計算
    watcher.py                 監視スレッド(全走査 0.3秒ごと / 乗っている窓だけ約10msごと)
    surface_map.py             足場の地図(着地判定・追従・補正)
    planner.py                 別ウィンドウへのジャンプの初速の計算
    walkways.py                Pet に注入される窓口(WalkSurfaces)
  imaging/                   【画像管理】
    lru.py                     バイト数上限つきLRU
    backend.py                 Qt の画像処理(読込・縮小・反転・ロスレス圧縮)
    store.py                   2層キャッシュ・世代管理・読み込みスレッド・先読み
  animation/                 【アニメーション管理】
    animation.py               連番1セット。「いま表示するコマ」を返す
    sprites.py                 assets/<状態>/ を束ねる。サイズ変更・起動時の優先読み込み
    placeholder.py             素材が無いときの簡易キャラ
  audio/voice.py             【音声再生】語録の再生
  ui/                        【画面】
    pet.py                     キャラクター本体(ウィンドウ・物理・入力・描画)
    settings.py                設定ダイアログ
    screens.py                 Qt の画面情報 → 足場計算用の ScreenInfo
  startup/                   【起動時読み込み】
    loading_window.py          「読み込み中」画面
    bootstrap.py               起動の進行役(組み立て役)
  app.py                     QApplication を作って Bootstrap を動かす
tools/check_architecture.py  依存関係の自動検査
tests/                       検証スクリプト(PySide6なしで中核ロジックを検証)
```

## 依存の規則(上位 → 下位の一方向のみ)

```
app → startup → ui ─────────→ surfaces ─→ system ─┐
           │          └──────────────────────────┤
           ├→ animation → imaging ──────────────┤→ diagnostics → config
           └→ audio ────────────────────────────┘
```

* **ui は animation / audio / imaging / system の取得口を import しない。** Pet は Sprites・VoicePlayer・
  WalkSurfaces を引数で受け取る(依存性注入)。組み立ては startup/bootstrap.py だけが行う。
* **system の中も「契約(window_api)」と「選択(window_factory)」を分ける**(選択が各OSの実装を import し、
  各実装が契約を import するため、同じファイルに置くと循環する)。
* 相対 import は使わない(`from mascot.xxx import ...` に統一)。
* `__init__.py` には処理を書かない(循環インポートの温床になるため)。
* 関数の中での遅延 import も同じ規則で検査される。
* 規則の本体は `tools/check_architecture.py` の `ALLOWED`。**新しいパッケージや依存を足すときは、
  先に ALLOWED を更新してから実装する。** 変更のたびに `python tools/check_architecture.py` を実行する。

## 起動の流れ

`app.run()` → ログ設定 → `QApplication` → `Bootstrap.start()`
1. 読み込み画面を表示(LoadingWindow)
2. `Sprites` を作る(素材確認。画像本体は読まない)→ 必須コマを読み込みスレッドへ依頼
3. 並行して `VoicePlayer` を初期化
4. 必須コマが揃う(またはタイムアウト)→ `Pet(cfg, sprites, voice)` を表示 → 読み込み画面を閉じる

## 機能追加の置き場所(案)

| 追加したい機能 | 置き場所 | 依存してよい先(ALLOWED に追加) |
|---|---|---|
| 会話機能 | `mascot/conversation/` を新設 | config, diagnostics, audio |
| ウィンドウ上の歩行 | **実装済み**(`system/window_*.py` + `surfaces/`)。下の節を参照 | - |
| 複数OS対応 | OS依存の処理は `mascot/system/` に集める | config |

* 会話機能は Pet を直接 import せず、Bootstrap が `Pet` に渡す(または Qt の Signal でやり取りする)。

## ウィンドウ上の歩行(実装済み)

* キャラクターは「画面下端」に加えて、**他アプリのウィンドウの上端**を歩く。端に着くと折り返す(65%)か、
  飛び降りる(35%)。歩き始めに、届く範囲の別ウィンドウへジャンプすることがある。
* 落下・ジャンプ・着地は**既存の FALL 状態と重力**を使う(ジャンプ=計算した初速で FALL に入るだけ)。
* 取得は毎フレームではない: 全走査は0.3秒ごと(別スレッド)、乗っている窓の位置だけ約10msごと。
* 手前のウィンドウに隠れた部分・画面に全身が収まらない高さ(最大化など)・使える範囲外は足場にならない。
* 設定の「他のウィンドウの上を歩く」でオフにできる(config: `walk_on_windows`)。

| OS | 実装 | 追加ライブラリ | 状態 |
|---|---|---|---|
| Windows | `window_win32.py`(ctypes) | 不要 | 実機未検証(判断ロジックは偽APIでテスト済み) |
| macOS | `window_macos.py` | `pyobjc-framework-Quartz` | 実機未検証 |
| Linux X11 | `window_x11.py` | `python-xlib` | 実機未検証 |
| Linux Wayland | (無効) | - | OSの仕様で他アプリの位置を取得できない。画面下端のみ歩く |

* 使えない環境(ライブラリ無し・Wayland・取得失敗が続いた場合)では自動で画面下端だけの歩行に戻り、
  理由は設定画面に表示される(`mascot.log` にも記録)。
* 権限: Windows は不要。macOS は位置・大きさ・レイヤーだけを読み、タイトルは読まないので、画面収録の許可は
  不要な想定(未検証)。もし必要になった場合は取得が空になり、画面下端のみの歩行になる。
* 座標: OSの生の座標(Windows/X11 はデバイスピクセル)を、Qt の座標へ変換して使う
  (`surfaces/geometry.py`。複数モニター・拡大率違いの変換は実機で未検証)。
* 注意: 「常に最前面に表示」をオフにしていると、ウィンドウをクリックしたときキャラクターがその後ろに
  隠れることがある。この機能を使うときは併用を推奨。

## 未実施の分割(次の段階の候補)

* `ui/pet.py`(約470行)は、ウィンドウ・物理(歩行/落下/壁)・入力(クリック/ドラッグ)・描画・メニューが
  1クラスに同居している。今回は「機能維持」を優先して手を入れていない。
  分けるなら、物理(`ui/physics.py`)→ 描画(`ui/painter.py`)の順が安全。
* 分割の前に、Pet の物理計算を Qt から切り離した単体テストを用意すること。
