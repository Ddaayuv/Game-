<?php
require __DIR__ . '/config.php';

// Railway public URL must be stored in the PUBLIC_URL environment variable.
// Example: https://your-app.up.railway.app
$publicUrl = rtrim((string)getenv('PUBLIC_URL'), '/');

if (!$publicUrl) {
    exit("PUBLIC_URL is not configured.\n");
}

$webhookUrl = $publicUrl . '/index.php';

$ch = curl_init(TG_API . 'setWebhook');
curl_setopt_array($ch, [
    CURLOPT_RETURNTRANSFER => true,
    CURLOPT_POST => true,
    CURLOPT_POSTFIELDS => [
        'url' => $webhookUrl,
        'drop_pending_updates' => 'true',
    ],
    CURLOPT_TIMEOUT => 30,
]);

$response = curl_exec($ch);
curl_close($ch);

header('Content-Type: application/json; charset=utf-8');
echo $response ?: json_encode(['ok' => false, 'description' => 'Telegram API request failed']);
