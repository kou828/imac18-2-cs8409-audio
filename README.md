# iMac18,2 CS8409 Audio Prototype

> **実験用のカーネルドライバーです。** 対象外の機種やカーネルでは使わないでください。カーネルモジュールの不具合はOS全体の停止、再起動、データ損失を起こすことがあります。このリポジトリにはインストール処理やビルド済みモジュールを含めていません。

[日本語](#日本語) | [English](#english)

## 日本語

### 免責事項

本ソフトウェアおよび関連情報は「現状有姿」で提供され、動作、安全性、特定目的への適合性について保証しません。本ソフトウェアの閲覧、ビルド、インストール、ロード、使用により、PCや周辺機器の故障・損傷、OSの停止、データの消失その他の損害が発生した場合、適用法令で認められる最大限の範囲で、著作権者および貢献者は責任を負いません。使用の判断、バックアップおよび復旧手段の準備は利用者の責任です。この免責は、適用法令上免責できない責任を排除しません。これは [GPL-2.0 の保証否認・責任制限](https://www.gnu.org/licenses/old-licenses/gpl-2.0.en.html) を補足する説明です。

iMac18,2 の Cirrus Logic CS8409/CS42L83 音声コーデックで、内蔵マイクの録音開始経路を試作したドライバーです。既存のCS8409コードを基に、対象機種の動的ADC選択時にApple固有の録音初期化を呼び出す変更を加えています。音声処理全体を書き直すものではありません。

この変更は1台の iMac18,2 で動作し、内蔵マイクから音声チャットアプリが応答することを確認しました。録音開始・停止の反復確認は20回すべて正常終了しました。これは独立した再現試験や長期安定性の保証ではありません。10分連続音声チャット、長時間録音、複数回の冷間起動、他のiMac・カーネル版は未検証です。

### 対象と検証環境

- 機種: Apple iMac18,2
- 音声: Cirrus Logic CS8409 / CS42L83、PCI subsystem ID `0x106b0f00`
- 検証環境: Zorin OS 18.1、Linux `7.0.0-34-generic`
- 機能確認: 内蔵マイクを使った音声チャットの応答、10秒録音20回
- **未検証**: 他機種・他カーネル、長期安定性、スリープ復帰

### ビルドと検査

Debian/Ubuntu系の対象Linuxカーネル上で、同じカーネル版のヘッダーを用意してください。必要なツールは `build-essential`, `linux-headers-$(uname -r)`, `python3`, `ripgrep`, `pahole` (`dwarves` パッケージ) です。

```sh
./check.sh
./build.sh "$(uname -r)"
```

ビルドはソース内に `.ko` を作るだけで、インストール、ロード、initramfs変更、再起動はしません。ABI確認全体が実施不能または不一致の場合はビルド失敗です。検査ログに個別の `not in BTF` 項目が出た場合は、その型が実際に共有・参照されないことを別途確認してください。ABI検査だけを根拠にモジュールをロードしないでください。確認を飛ばしてロードする手順は提供していません。

### 実機試験について

このリポジトリは、ドライバーを自動インストールしません。専用テスト環境と復旧手段を用意し、手動で適用してください。普段使うOSへの適用は推奨しません。候補モジュールを実機へ読み込む前に、対象カーネルの正確な共有構造体ABIを確認してください。公開済みのビルド済み`.ko`を使用しないでください。

音声レベルを補助確認する `collect-levels.py` はPCMをファイルに保存せず、メモリー内で統計値だけを表示します。ALSAデバイス名は環境に応じて指定してください。

### 内蔵スピーカーのブツブツ音（任意設定）

`config/90-imac-audio-buffer.conf` はPipeWireの最小quantumを512サンプルにするユーザー単位の設定例です。1台でYouTube再生のブツブツ音が解消しましたが、環境によって音声遅延が増える場合があります。

```sh
mkdir -p ~/.config/pipewire/pipewire.conf.d
cp config/90-imac-audio-buffer.conf ~/.config/pipewire/pipewire.conf.d/
systemctl --user restart pipewire pipewire-pulse wireplumber
```

戻すときはコピーした設定ファイルを削除し、同じユーザーサービスを再起動します。

### ライセンスと由来

GPL-2.0-only。元のCS8409コードは [armin-haghi/imac-cs8409-linux-audio](https://github.com/armin-haghi/imac-cs8409-linux-audio) のコミット [`b08d0745e1b78d6949d5a231d91351e73ddf8079`](https://github.com/armin-haghi/imac-cs8409-linux-audio/tree/b08d0745e1b78d6949d5a231d91351e73ddf8079) に基づきます。Linuxカーネル由来のファイルおよび各ファイル内の著作権表示も保持しています。詳細は [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) を参照してください。

## English

### Disclaimer

This software and related information are provided “as is,” without warranties of operation, safety, or fitness for a particular purpose. To the maximum extent permitted by applicable law, the copyright holders and contributors accept no liability for damage to a computer or peripheral equipment, system failure, data loss, or other damages arising from viewing, building, installing, loading, or using this software. You are responsible for deciding whether to use it and for preparing backups and a recovery method. This disclaimer does not exclude liability that cannot be excluded under applicable law. It supplements the warranty disclaimer and limitation of liability in [GPL-2.0](https://www.gnu.org/licenses/old-licenses/gpl-2.0.en.html).

An experimental CS8409/CS42L83 driver prototype for the built-in microphone on Apple iMac18,2. It adds a machine-specific callback for Apple microphone initialization when the existing driver dynamically selects an ADC. It builds on existing CS8409 code; it does not replace the audio stack.

The change was functionally checked on one iMac18,2: a voice-chat application responded through the built-in microphone, and twenty 10-second capture start/stop cycles completed. This is not an independent reproduction or a long-term stability guarantee. Ten-minute voice-chat sessions, long captures, multiple cold boots, other iMac models, and other kernels have not been tested.

- Tested machine: iMac18,2, CS8409/CS42L83, subsystem ID `0x106b0f00`
- Tested OS/kernel: Zorin OS 18.1, Linux `7.0.0-34-generic`
- Build and checks: run `./check.sh` and `./build.sh "$(uname -r)"` with matching kernel headers and the listed tools. The build does not install or load the module.
- No installer or prebuilt module is provided. Use only in a dedicated test environment with a recovery path.
- The optional PipeWire quantum setting was tested on one system and may increase latency.
- License: GPL-2.0-only; see `LICENSE` and `THIRD_PARTY_NOTICES.md`.
