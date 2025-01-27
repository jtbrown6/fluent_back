from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
import openai
import os
import json
from dotenv import load_dotenv
import logging
import re
import threading

load_dotenv()

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Set your OpenAI API key securely
openai.api_key = os.getenv('OPENAI_API_KEY')  # Ensure you have set this environment variable

# @app.route('/')
# def index():
#     return render_template('index.html')


# How we can handle the in-memory storage for conversations
# Data Struct: {user_id: { message1, message2, ...}}
conversation_history = []
MAX_HISTORY = 3  # Number of user messages to keep

# We are stopping the number of messages for the total tokens sent
MAX_HISTORY = 3


# This handles the "Assist Me" Button
@app.route('/api/assist', methods=['POST'])
def assist():
    data = request.json
    text = data.get('text', '')
    messages = [
        {"role": "system", "content": "You are a helpful assistant proficient in correcting Spanish text."},
        {"role": "user", "content": f"Correct the following Spanish text, consider any cultural or situational nuances and explain any mistakes:\n\n{text}"}
    ]
    response = openai.ChatCompletion.create(
        model='gpt-4o-mini',
        messages=messages,
        max_tokens=900,
        temperature=0.7,
    )
    return jsonify({'result': response.choices[0].message['content'].strip()})



# This handles the conjugate button and table
@app.route('/api/conjugate', methods=['POST'])
def conjugate():
    data = request.json
    verb = data.get('verb', '')
    logger.debug(f"Received request to conjugate verb: {verb}")
    
    messages = [
        {"role": "system", "content": "You are a helpful assistant proficient in Spanish verb conjugations."},
        {"role": "user", "content": f"Provide the conjugations of the Spanish verb '{verb}' in the following tenses: present, subjunctive, preterite, imperfect, and future. Do not include 'vosotros' forms. Return ONLY the JSON data with keys for each tense ('present', 'subjunctive', etc.), and for each tense, provide a dictionary with keys 'yo', 'tú', 'él/ella/usted', 'nosotros', 'ellos/ellas/ustedes', and their corresponding conjugations."}
    ]
    
    try:
        response = openai.ChatCompletion.create(
            model='gpt-4o-mini',
            messages=messages,
            max_tokens=700,
            temperature=0.7,
        )
        logger.debug(f"Received response from OpenAI: {response}")
        
        content = response.choices[0].message['content'].strip()
        logger.debug(f"Extracted content: {content}")
        
        # Extract JSON content
        json_match = re.search(r'\{[\s\S]*\}', content)
        if json_match:
            json_content = json_match.group(0)
            logger.debug(f"Extracted JSON content: {json_content}")
            
            conjugations = json.loads(json_content)
            logger.debug(f"Parsed conjugations: {conjugations}")
            
            return jsonify({'result': conjugations})
        else:
            logger.error("No JSON content found in the response")
            return jsonify({'error': 'No JSON content found in the response', 'raw_response': content})
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error: {str(e)}")
        return jsonify({'error': 'Failed to parse conjugations', 'raw_response': content})
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return jsonify({'error': 'An unexpected error occurred', 'details': str(e)})


@app.route('/api/define', methods=['POST'])
def define():
    data = request.json
    word = data.get('word', '')
    messages = [
        {"role": "system", "content": "You are a helpful assistant proficient in defining Spanish words in English and vice versa."},
        {"role": "user", "content": f"Define the Spanish or English word '{word}' in English or Spanish and provide a sentence using the word. If the word has both a definition for its form as a noun or adjective provide both."}
    ]
    response = openai.ChatCompletion.create(
        model='gpt-4o-mini',
        messages=messages,
        max_tokens=200,
        temperature=0.7,
    )
    return jsonify({'result': response.choices[0].message['content'].strip()})


# Handles the Chat Window Feature w/ History 
SYSTEM_PROMPT = {
    "role": "system",
    "content": "You are a helpful assistant for Spanish language learning. Consider cultural and situational nuances while assisting."
}
conversation_history.append(SYSTEM_PROMPT.copy())

@app.route('/api/chatbot', methods=['POST'])
def question():
    data = request.json
    query = data.get('query', '').strip()

    if not query:
        logger.debug("Received empty query.")
        return jsonify({'error': 'Missing or empty query in request'}), 400
    
    # Append the user message
    conversation_history.append({"role": "user", "content": query})
    logger.debug(f"Appended user message: {query}")
    
    # Prune conversation history to keep only the last MAX_HISTORY user messages and their assistant responses
    # Including system prompt
    # Find indices of all user messages
    user_indices = [i for i, msg in enumerate(conversation_history) if msg['role'] == 'user']
    
    if len(user_indices) > MAX_HISTORY:
        # Calculate the index to start keeping messages
        keep_from = user_indices[-MAX_HISTORY]
        # Retain system prompt and messages from keep_from onwards
        pruned_history = [SYSTEM_PROMPT.copy()] + conversation_history[keep_from:]
        conversation_history[:] = pruned_history
        logger.debug(f"Pruned conversation history to keep last {MAX_HISTORY} user messages.")

    # Prepare messages to send to OpenAI
    messages_to_send = conversation_history.copy()
    logger.debug(f"Messages sent to OpenAI: {json.dumps(messages_to_send, ensure_ascii=False)}")

    try:
        response = openai.ChatCompletion.create(
        model='gpt-4o-mini',
        messages=messages_to_send,
        max_tokens=500,
        temperature=0.7,
    )
        assistant_message = response.choices[0].message['content'].strip()
        logger.debug(f"Assistant response: {assistant_message}")

        # Append assistant response to the history
        conversation_history.append({"role": "assistant", "content": assistant_message})
        logger.debug("Appended assistant message to conversation history.")   

        
        return jsonify({'result': assistant_message})
    except Exception as e:
        logger.error(f"Error communicating with OpenAI: {str(e)}")
        return jsonify({'error': 'Failed to get response from assistant', 'details': str(e)}), 500

    # Example endpoint to reset conversation (optional)
@app.route('/api/reset_conversation', methods=['POST'])
def reset_conversation():
    conversation_history.clear()
    conversation_history.append(SYSTEM_PROMPT.copy())
    logger.debug("Conversation history has been reset.")
    return jsonify({'result': 'Conversation history reset successfully'})


if __name__ == '__main__':
    app.run(host='0.0.0.0', debug=True)


