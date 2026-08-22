import pytest
from unittest.mock import patch, MagicMock
from src.notifications.telegram import TelegramNotifier
from src.notifications.notifier import NotificationManager

def test_telegram_notifier_unconfigured():
    notifier = TelegramNotifier(bot_token=None, chat_id=None)
    assert notifier.is_configured is False
    assert notifier.send_message("Hello") is False

def test_telegram_notifier_configured_mock():
    notifier = TelegramNotifier(bot_token="test_token", chat_id="123456789")
    assert notifier.is_configured is True
    
    with patch("urllib.request.urlopen") as mock_urlopen:
        mock_response = MagicMock()
        mock_response.status = 200
        mock_urlopen.return_value.__enter__.return_value = mock_response
        
        success = notifier.send_message("Test message")
        assert success is True
        mock_urlopen.assert_called_once()

def test_notification_manager_dispatchers():
    # Verify all notification helper methods run cleanly without raising errors
    NotificationManager.notify_human_intervention("TestCorp", "AI Engineer", "CAPTCHA detected")
    NotificationManager.notify_application_status("TestCorp", "AI Engineer", "READY_TO_SUBMIT")
    NotificationManager.notify_daily_summary(discovered=10, qualified=4, submitted=2, skipped=6)
