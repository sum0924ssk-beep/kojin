document.addEventListener("DOMContentLoaded", async () => {
    // 必須要素の参照
    const video = document.getElementById("camera");
    const canvas = document.getElementById("photoCanvas");
    const fileInput = document.getElementById("fileInput");
    const captureButton = document.querySelector(".custom-file-upload"); // 撮影ボタンとして扱う

    // 要素が存在しない場合は処理を中断
    if (!video || !canvas || !fileInput || !captureButton) {
        console.error("必須のHTML要素が見つかりません。ID/クラスを確認してください。");
        return;
    }

    let isCameraReady = false;

    try {
        // 1. カメラ起動 (要: HTTPS接続とユーザー許可)
        const stream = await navigator.mediaDevices.getUserMedia({
            video: { 
                // モバイル環境での背面カメラ優先
                facingMode: "environment" 
            }
        });
        video.srcObject = stream;
        
        // 2. ストリームの準備完了を待つ
        video.onloadedmetadata = () => {
            console.log("カメラストリームの準備ができました。");
            isCameraReady = true;
            // ユーザーに撮影可能になったことを伝えるなど（任意）
            captureButton.textContent = "📸 写真を撮影する"; 
        };

    } catch (err) {
        console.error("🔴 カメラ起動エラー:", err);
        // エラーメッセージをユーザーに分かりやすく表示
        alert("カメラにアクセスできません。権限を確認するか、HTTPS接続になっているか確認してください。");
        captureButton.textContent = "カメラ使用不可";
        captureButton.disabled = true;
        return;
    }

    // 📸 撮影ボタンクリック時の処理
    captureButton.addEventListener("click", (event) => {
        // デフォルトのファイル選択ダイアログの動作を阻止
        event.preventDefault(); 

        if (!isCameraReady || !video.srcObject) {
            alert("カメラがまだ準備できていません。しばらく待ってから再度お試しください。");
            return;
        }

        const context = canvas.getContext("2d");
        
        // 適切な解像度でキャプチャ
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        context.drawImage(video, 0, 0, canvas.width, canvas.height);

        // Canvas を Blob に変換して仮想の File としてフォームに渡す
        canvas.toBlob((blob) => {
            if (!blob) {
                alert("キャプチャに失敗しました。");
                return;
            }
            
            // ファイルオブジェクトの作成
            const file = new File([blob], "capture_" + Date.now() + ".jpeg", { type: "image/jpeg" });
            
            // DataTransferを使用してinput[type=file]に値をセット
            const dataTransfer = new DataTransfer();
            dataTransfer.items.add(file);
            fileInput.files = dataTransfer.files;
            
            alert("✅ 写真を撮影しました！ファイルがセットされました。");
            console.log("ファイルが正常にセットされました:", file);
            
        }, "image/jpeg", 0.9); // JPEG形式、品質0.9
    });
});