document.addEventListener("DOMContentLoaded", async () => {
    // 必須要素の参照
    const video = document.getElementById("camera");
    const canvas = document.getElementById("photoCanvas");
    const fileInput = document.getElementById("fileInput");
    // label要素を参照（カスタム撮影ボタンとして使用）
    const captureButton = document.querySelector(".custom-file-upload"); 

    // HTML要素の参照が失敗した場合に処理を中断
    if (!video || !canvas || !fileInput || !captureButton) {
        console.error("🔴 必須のHTML要素が見つかりません。ID/クラスを確認してください。");
        // ボタンを無効化してユーザーにフィードバック
        if (captureButton) {
            captureButton.textContent = "設定エラー";
            // labelはdisabled属性がないため、ここではCSSなどで無効に見せる処理が必要です
        }
        return;
    }

    let isCameraReady = false;

    try {
        // 1. カメラ起動 (HTTPS接続とユーザー許可が必須)
        const stream = await navigator.mediaDevices.getUserMedia({
            video: { 
                facingMode: "environment" // 背面カメラを優先
            }
        });
        video.srcObject = stream;
        
        // 2. ストリームの準備完了を待つ
        video.onloadedmetadata = () => {
            console.log("カメラストリームの準備ができました。");
            isCameraReady = true;
            captureButton.textContent = "📸 写真を撮影する"; 
        };

    } catch (err) {
        console.error("🔴 カメラ起動エラー:", err);
        alert("カメラにアクセスできません。権限を確認するか、サイトがHTTPS接続になっているか確認してください。");
        captureButton.textContent = "カメラ使用不可";
        // ボタンを無効化する代わりに、クリックイベントが発生しないようにフラグをfalseのままにする
        return;
    }

    // 📸 撮影ボタンクリック時の処理
    captureButton.addEventListener("click", (event) => {
        // label要素が本来持つ input[type=file] を開く動作を阻止
        event.preventDefault(); 

        if (!isCameraReady || !video.srcObject) {
            alert("カメラがまだ準備できていません。しばらく待ってから再度お試しください。");
            return;
        }

        const context = canvas.getContext("2d");
        
        // 映像のサイズに合わせてCanvasを設定
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        context.drawImage(video, 0, 0, canvas.width, canvas.height);

        // Canvas を Blob に変換して input[type=file] にセット
        canvas.toBlob((blob) => {
            if (!blob) {
                alert("キャプチャに失敗しました。");
                return;
            }
            
            const file = new File([blob], "captured_item.jpeg", { type: "image/jpeg" });
            const dataTransfer = new DataTransfer();
            dataTransfer.items.add(file);
            fileInput.files = dataTransfer.files;
            
            alert("✅ 写真を撮影しました！フォームにセットされています。");
            
        }, "image/jpeg", 0.9);
    });
});