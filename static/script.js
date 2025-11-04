// static/script.js
document.addEventListener("DOMContentLoaded", async () => {
    // === 要素の取得 ===
    const video = document.getElementById("camera");
    const canvas = document.getElementById("photoCanvas");
    const fileInput = document.getElementById("fileInput");
    const captureButton = document.querySelector(".custom-file-upload");

    // === 必須要素チェック ===
    if (!video || !canvas || !fileInput || !captureButton) {
        console.warn("⚠️ カメラ関連の要素が見つかりません。撮影機能をスキップします。");
        return;
    }

    let isCameraReady = false;
    let stream = null;

    // === カメラ起動処理 ===
    try {
        stream = await navigator.mediaDevices.getUserMedia({
            video: { facingMode: { ideal: "environment" } },
            audio: false,
        });
        video.srcObject = stream;

        video.addEventListener("loadedmetadata", () => {
            isCameraReady = true;
            captureButton.textContent = "📸 撮影する";
            console.log("✅ カメラが準備完了しました。");
        });
    } catch (err) {
        console.error("❌ カメラ起動エラー:", err);
        alert("カメラを利用できません。ブラウザの設定やHTTPS接続を確認してください。");
        captureButton.disabled = true;
        captureButton.textContent = "カメラ使用不可";
        return;
    }

    // === 撮影処理 ===
    captureButton.addEventListener("click", async (e) => {
        e.preventDefault();

        if (!isCameraReady) {
            alert("カメラがまだ準備中です。少し待ってからお試しください。");
            return;
        }

        try {
            const ctx = canvas.getContext("2d");
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

            // Blob化
            const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.9));
            if (!blob) throw new Error("Blob変換に失敗しました。");

            const file = new File([blob], `capture_${Date.now()}.jpeg`, { type: "image/jpeg" });

            // FileInput にセット
            const dt = new DataTransfer();
            dt.items.add(file);
            fileInput.files = dt.files;

            alert("📷 撮影完了！フォームに写真をセットしました。");

        } catch (err) {
            console.error("撮影処理中のエラー:", err);
            alert("撮影中にエラーが発生しました。もう一度お試しください。");
        }
    });

    // === ページ離脱時にカメラを停止 ===
    window.addEventListener("beforeunload", () => {
        if (stream) {
            stream.getTracks().forEach((track) => track.stop());
        }
    });
});
