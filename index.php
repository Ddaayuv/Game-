<?php
require __DIR__ . '/config.php';

function tg(string $method, array $data = []): ?array {
    $ch = curl_init(TG_API . $method);
    curl_setopt_array($ch, [
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_POST => true,
        CURLOPT_POSTFIELDS => $data,
        CURLOPT_TIMEOUT => 30,
    ]);

    $response = curl_exec($ch);
    curl_close($ch);

    return $response ? json_decode($response, true) : null;
}

function sendText($chatId, string $text): void {
    tg('sendMessage', [
        'chat_id' => $chatId,
        'text' => $text,
    ]);
}

function createQr(string $text): ?string {
    $url = 'https://api.qrserver.com/v1/create-qr-code/?size=800x800&format=png&data='
         . rawurlencode($text);

    $ch = curl_init($url);
    curl_setopt_array($ch, [
        CURLOPT_RETURNTRANSFER => true,
        CURLOPT_FOLLOWLOCATION => true,
        CURLOPT_TIMEOUT => 30,
        CURLOPT_USERAGENT => 'Railway-Telegram-QR-Bot/1.0',
    ]);

    $image = curl_exec($ch);
    $httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
    curl_close($ch);

    if ($httpCode !== 200 || !$image || strlen($image) < 100) {
        return null;
    }

    $file = tempnam(sys_get_temp_dir(), 'qr_') . '.png';
    file_put_contents($file, $image);

    return $file;
}

$update = json_decode(file_get_contents('php://input'), true);

if (!$update || empty($update['message']['chat']['id'])) {
    echo 'OK';
    exit;
}

$chatId = $update['message']['chat']['id'];
$text = trim($update['message']['text'] ?? '');

if ($text === '/start') {
    sendText(
        $chatId,
        "👋 أهلاً بك!\n\nأرسل أي نص أو رابط وسأحوّله إلى QR Code حقيقي.\n\nمثال:\nhttps://example.com"
    );
    exit('OK');
}

if ($text === '/help') {
    sendText($chatId, "📌 أرسل أي نص أو رابط وسأرجعه لك كصورة QR Code.");
    exit('OK');
}

if ($text === '') {
    exit('OK');
}

if (mb_strlen($text, 'UTF-8') > 4000) {
    sendText($chatId, "❌ النص طويل جدًا. الحد الأقصى 4000 حرف.");
    exit('OK');
}

$qrFile = createQr($text);

if (!$qrFile) {
    sendText($chatId, "❌ تعذر إنشاء QR الآن. حاول مرة أخرى.");
    exit('OK');
}

$result = tg('sendPhoto', [
    'chat_id' => $chatId,
    'photo' => new CURLFile($qrFile, 'image/png', 'qrcode.png'),
    'caption' => "✅ تم إنشاء QR Code بنجاح",
]);

@unlink($qrFile);

if (empty($result['ok'])) {
    sendText($chatId, "❌ حدث خطأ أثناء إرسال QR إلى Telegram.");
}

echo 'OK';
