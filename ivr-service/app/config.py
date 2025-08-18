class VoiceConfig:
    """Voice configuration for different languages"""
    VOICE_MAP = {
        "English": {"voice": "Polly.Raveena", "language": "en-IN"},
        "Hindi": {"voice": "Polly.Aditi", "language": "hi-IN"},
        "Marathi": {"voice": "Polly.Aditi", "language": "hi-IN"}
    }
    
    @staticmethod
    def get_voice_config(language):
        return VoiceConfig.VOICE_MAP.get(language, VoiceConfig.VOICE_MAP["English"])


class LanguageConfig:
    """Language selection configuration"""
    LANGUAGE_MAP = {
        "1": "English",
        "2": "Hindi",
        "3": "Marathi"
    }
    
    PROMPTS = {
        "English": {
            "welcome": "For English, press 1. For Hindi, press 2. For Marathi, press 3.",
            "selected": "You selected English. Please state your query after the beep. Press hash when done.",
            "processing": "Thank you. We're processing your request. Please wait.",
            "still_processing": "Still processing your request. Please continue holding.",
            "error": "Processing error. Please try again later.",
            "goodbye": "Thank you for your query. Goodbye!"
        },
        "Hindi": {
            "welcome": "अंग्रेजी के लिए 1 दबाएं. हिंदी के लिए 2 दबाएं. मराठी के लिए 3 दबाएं.",
            "selected": "आपने हिंदी चुनी है। कृपया बीप के बाद अपना प्रश्न बोलें। समाप्त करने के लिए हैश दबाएँ।",
            "processing": "धन्यवाद। हम आपका अनुरोध प्रक्रिया कर रहे हैं। कृपया प्रतीक्षा करें।",
            "still_processing": "अभी भी आपका अनुरोध प्रक्रिया में है। कृपया प्रतीक्षा करते रहें।",
            "error": "प्रक्रिया में त्रुटि। कृपया बाद में पुनः प्रयास करें।",
            "goodbye": "आपके प्रश्न के लिए धन्यवाद। अलविदा!"
        },
        "Marathi": {
            "welcome": "इंग्रजीसाठी 1 दाबा. हिंदीसाठी 2 दाबा. मराठीसाठी 3 दाबा.",
            "selected": "तुम्ही मराठी निवडले आहे. कृपया बीप नंतर आपला प्रश्न सांगा. समाप्त करण्यासाठी हॅश दाबा.",
            "processing": "धन्यवाद. आम्ही तुमची विनंती प्रक्रिया करत आहोत. कृपया प्रतीक्षा करा.",
            "still_processing": "अजूनही तुमची विनंती प्रक्रियाधीन आहे. कृपया प्रतीक्षा करत रहा.",
            "error": "प्रक्रिया त्रुटी. कृपया नंतर पुन्हा प्रयत्न करा.",
            "goodbye": "तुमच्या प्रश्नासाठी धन्यवाद. निरोप!"
        }
    }