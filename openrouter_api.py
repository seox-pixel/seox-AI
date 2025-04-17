from flask import Flask, render_template, request, jsonify
import requests
import json
import os
import logging
from logging.handlers import RotatingFileHandler

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def call_openrouter_api(keyword):
    """
    Call the OpenRouter API to get keyword suggestions
    """
    url = "https://openrouter.ai/api/v1/chat/completions"
    
    # API key
    api_key = "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"
    
    # Headers
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "https://localhost:3000"
    }
    
    # Prepare the prompt for the AI
    system_prompt = """You are an SEO expert assistant. Your task is to provide keyword suggestions based on the user's input.
For the given keyword or phrase, provide exactly 10 high-ranking SEO keyword suggestions.
For each suggestion, include:
1. The keyword itself
2. A short description (1-2 sentences)
3. The estimated user intent (informational, transactional, navigational, or commercial investigation)
4. A suggested content angle for this keyword

Format your response as a JSON array with objects containing these fields:
[
  {
    "keyword": "example keyword",
    "description": "Short description of the keyword",
    "intent": "User intent category",
    "angle": "Content angle suggestion"
  },
  ...
]

Only return the JSON array, no other text."""
    
    # Prepare the payload - using a valid model ID from OpenRouter
    payload = {
        "model": "openai/gpt-3.5-turbo",  # Changed from "openchat/openchat-3.5" to a valid model
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Provide SEO keyword suggestions for: {keyword}"}
        ]
    }
    
    try:
        logger.info(f"Sending request to OpenRouter API for keyword: {keyword}")
        # Make the API call
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        
        # Check for rate limiting or quota exceeded
        if response.status_code == 429:
            logger.error("API rate limit or quota exceeded")
            return {"success": False, "error": "API rate limit or quota exceeded. Please try again later."}
        
        # Check for other HTTP errors
        response.raise_for_status()
        
        # Parse the response
        result = response.json()
        logger.info("Successfully received response from OpenRouter API")
        
        # Extract the content from the response
        if 'choices' in result and len(result['choices']) > 0:
            content = result['choices'][0]['message']['content']
            
            # Parse the JSON content
            try:
                # Clean the content if it contains markdown code blocks
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()
                
                keywords_data = json.loads(content)
                
                # Validate the structure of the response
                if not isinstance(keywords_data, list):
                    logger.error("API response is not a list")
                    return {"success": False, "error": "Invalid API response format"}
                
                # Ensure we have exactly 10 keywords or at least some results
                if len(keywords_data) == 0:
                    logger.warning("API returned empty results")
                    return {"success": False, "error": "No keyword suggestions found. Please try a different search term."}
                
                # Validate each keyword item has the required fields
                for item in keywords_data:
                    if not all(key in item for key in ["keyword", "description", "intent", "angle"]):
                        logger.error("API response missing required fields")
                        return {"success": False, "error": "Invalid API response structure"}
                
                return {"success": True, "data": keywords_data}
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse API response: {str(e)}")
                logger.error(f"Raw content: {content}")
                return {"success": False, "error": "Failed to parse API response. The service may be experiencing issues."}
        else:
            logger.error("No content in API response")
            return {"success": False, "error": "No content in API response. Please try again."}
            
    except requests.exceptions.Timeout:
        logger.error("API request timed out")
        return {"success": False, "error": "API request timed out. Please try again later."}
    except requests.exceptions.ConnectionError:
        logger.error("Connection error when calling API")
        return {"success": False, "error": "Connection error. Please check your internet connection and try again."}
    except requests.exceptions.RequestException as e:
        logger.error(f"API request failed: {str(e)}")
        return {"success": False, "error": f"API request failed: {str(e)}"}
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return {"success": False, "error": "An unexpected error occurred. Please try again later."}
