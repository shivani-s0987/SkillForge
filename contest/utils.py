import os
import re
import time
import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def discover_gemini_models(api_base=None, gemini_key=None, gemini_token=None, timeout=None):
    """Discover models available to the configured Gemini credentials.

    This is a lightweight helper so management commands can list available models
    for the current credentials. Returns list of tuples (root, model_obj).
    """
    api_base = api_base or getattr(settings, 'GEMINI_API_BASE', None) or os.environ.get('GEMINI_API_BASE', 'https://generativelanguage.googleapis.com')
    gemini_key = gemini_key or getattr(settings, 'GEMINI_API_KEY', None) or os.environ.get('GEMINI_API_KEY')
    gemini_token = gemini_token or getattr(settings, 'GEMINI_BEARER_TOKEN', None) or os.environ.get('GEMINI_BEARER_TOKEN')
    timeout = timeout or float(getattr(settings, 'GEMINI_TIMEOUT', os.environ.get('GEMINI_TIMEOUT', 20)))

    if not (gemini_key or gemini_token):
        logger.warning('Gemini credentials not provided for discovery.')
        return []

    roots = [api_base.rstrip('/')]
    if not api_base.endswith('/v1') and not api_base.endswith('/v1beta'):
        roots.extend([api_base.rstrip('/') + '/v1', api_base.rstrip('/') + '/v1beta'])

    models_found = []
    for root in roots:
        url = f"{root.rstrip('/')}/models"
        try:
            headers = {'Content-Type': 'application/json'}
            if gemini_token:
                headers['Authorization'] = f'Bearer {gemini_token}'
                resp = requests.get(url, headers=headers, timeout=timeout)
            else:
                resp = requests.get(url, params={'key': gemini_key}, timeout=timeout)
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, dict) and 'models' in data and isinstance(data['models'], list):
                    for m in data['models']:
                        models_found.append((root, m))
                elif isinstance(data, list):
                    for m in data:
                        models_found.append((root, m))
                else:
                    models_found.append((root, data))
            else:
                logger.debug('ListModels failed at %s: %s %s', url, resp.status_code, resp.text)
        except Exception as e:
            logger.debug('ListModels exception for %s: %s', url, e)
    return models_found


# -----------------------------
# OpenAI API CALL
# -----------------------------
def call_openai(prompt: str) -> str:
    """Safely call OpenAI API (GPT models)."""
    openai_key = os.environ.get('OPENAI_API_KEY') or getattr(settings, 'OPENAI_API_KEY', None)
    if not openai_key:
        logger.warning("OpenAI API key not configured.")
        return None

    try:
        url = "https://api.openai.com/v1/chat/completions"
        headers = {"Authorization": f"Bearer {openai_key}", "Content-Type": "application/json"}
        data = {
            "model": "gpt-3.5-turbo",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 300,
            "temperature": 0.3,
        }
        resp = requests.post(url, headers=headers, json=data, timeout=15)

        if resp.status_code == 200:
            payload = resp.json()
            return payload['choices'][0]['message']['content'].strip()
        else:
            logger.warning(f"OpenAI request failed [{resp.status_code}]: {resp.text}")
    except Exception as e:
        logger.exception("OpenAI call failed: %s", e)
    return None


# -----------------------------
# GEMINI API CALL
# -----------------------------
def call_gemini(prompt: str) -> str:
    """Call Google Gemini API with model discovery and robust endpoint selection.

    This function will attempt the configured model first. If it receives a 404
    mentioning the model or unsupported method, it will call the ListModels API
    (both v1 and v1beta roots) to discover available models and their supported
    methods and retry with a compatible model and method. Returns text output or
    None on failure.
    """
    gemini_key = getattr(settings, 'GEMINI_API_KEY', None) or os.environ.get('GEMINI_API_KEY')
    gemini_token = getattr(settings, 'GEMINI_BEARER_TOKEN', None) or os.environ.get('GEMINI_BEARER_TOKEN')
    model = getattr(settings, 'GEMINI_MODEL_NAME', None) or os.environ.get('GEMINI_MODEL_NAME')
    api_base = getattr(settings, 'GEMINI_API_BASE', None) or os.environ.get('GEMINI_API_BASE', 'https://generativelanguage.googleapis.com')
    retries = int(getattr(settings, 'GEMINI_RETRIES', os.environ.get('GEMINI_RETRIES', 1)))
    timeout = float(getattr(settings, 'GEMINI_TIMEOUT', os.environ.get('GEMINI_TIMEOUT', 60)))

    if not (gemini_key or gemini_token):
        logger.warning('Gemini credentials not provided (GEMINI_API_KEY or GEMINI_BEARER_TOKEN).')
        return None

    # Helper: list available models from the API root (tries v1 and v1beta)
    def list_models():
        roots = [api_base.rstrip('/')]
        # ensure both v1 and v1beta roots are checked
        if not api_base.endswith('/v1') and not api_base.endswith('/v1beta'):
            roots.extend([api_base.rstrip('/') + '/v1', api_base.rstrip('/') + '/v1beta'])
        models_found = []
        for root in roots:
            url = f"{root.rstrip('/')}/models"
            try:
                headers = {'Content-Type': 'application/json'}
                if gemini_token:
                    headers['Authorization'] = f'Bearer {gemini_token}'
                    resp = requests.get(url, headers=headers, timeout=timeout)
                else:
                    resp = requests.get(url, params={'key': gemini_key}, timeout=timeout)
                if resp.status_code == 200:
                    data = resp.json()
                    # Try to extract a models list from multiple shapes
                    if isinstance(data, dict) and 'models' in data and isinstance(data['models'], list):
                        for m in data['models']:
                            models_found.append((root, m))
                    elif isinstance(data, list):
                        for m in data:
                            models_found.append((root, m))
                    else:
                        # Single model object
                        models_found.append((root, data))
                else:
                    logger.debug('ListModels failed at %s: %s %s', url, resp.status_code, resp.text)
            except Exception as e:
                logger.debug('ListModels exception for %s: %s', url, e)
        return models_found

    # Use the top-level discover function when available
    try:
        # discover_gemini_models is exported at module level; prefer that if present
        from contest.utils import discover_gemini_models as _discover_top
    except Exception:
        _discover_top = None

    # Try preferred endpoints in order, but be prepared to discover models
    # We'll try the following candidate methods: generateContent (v1beta) and generateText (v1)
    tried = []
    last_exc = None

    # Candidate function to attempt a single model+method
    def try_model_method(root, model_name, method, attempt_index):
        nonlocal last_exc
        url = f"{root.rstrip('/')}/models/{model_name}:{method}"
        headers = {'Content-Type': 'application/json'}
        params = {'key': gemini_key} if gemini_key and not gemini_token else None

        if method == 'generateContent':
            payload = {"contents": [{"parts": [{"text": prompt}]}]}
        else:
            payload = {"prompt": prompt, "maxOutputTokens": 300}

        for attempt in range(retries + 1):
            try:
                # Use a connect/read timeout tuple to avoid long blocking on connect
                req_timeout = (5, timeout)  # connect timeout 5s, read timeout configured
                if gemini_token:
                    headers['Authorization'] = f'Bearer {gemini_token}'
                    resp = requests.post(url, headers=headers, json=payload, timeout=req_timeout)
                else:
                    resp = requests.post(url, headers=headers, params=params, json=payload, timeout=req_timeout)

                if resp.status_code == 200:
                    data = resp.json()
                    # parse multiple shapes
                    if isinstance(data, dict):
                        if 'candidates' in data and data['candidates']:
                            # v1beta generateContent shape
                            cand = data['candidates'][0]
                            # support nested content.parts
                            if isinstance(cand, dict) and 'content' in cand:
                                parts = cand['content'].get('parts') if isinstance(cand['content'], dict) else None
                                if parts and isinstance(parts, list) and parts[0].get('text'):
                                    return parts[0]['text']
                            # v1-like candidates
                            if isinstance(cand, dict):
                                for key in ('output', 'text', 'content'):
                                    v = cand.get(key)
                                    if isinstance(v, str) and v.strip():
                                        return v.strip()
                        if 'output' in data and isinstance(data['output'], str):
                            return data['output'].strip()
                        choices = data.get('choices') or []
                        if choices and isinstance(choices, list):
                            first = choices[0]
                            if isinstance(first, dict):
                                if first.get('content'):
                                    return first.get('content').strip()
                                if first.get('message') and first['message'].get('content'):
                                    return first['message']['content'].strip()
                    # fallback to raw text
                    text = resp.text
                    if text:
                        return text.strip()
                else:
                    # handle common failures
                    if resp.status_code == 404:
                        logger.warning('Gemini request failed [404]: %s\n (attempt %s/%s)\nInvalid model or method at URL: %s', resp.text, attempt+1, retries+1, url)
                        return None
                    if resp.status_code in (401, 403):
                        logger.warning('Gemini authentication/permission failed (%s). Check key/token and IAM permissions. Response: %s', resp.status_code, resp.text)
                        return None
                    logger.warning('Gemini request failed [%s]: %s (attempt %s/%s)', resp.status_code, resp.text, attempt+1, retries+1)
            except requests.exceptions.ReadTimeout as e:
                last_exc = e
                logger.warning('Read timeout calling Gemini %s (attempt %s/%s): %s', url, attempt+1, retries+1, e)
                # If read timeout, try next attempt quickly (don't sleep long)
            except Exception as e:
                last_exc = e
                logger.exception('Exception calling Gemini %s (attempt %s/%s): %s', url, attempt+1, retries+1, e)
            time.sleep(0.5 * (attempt + 1))
        return None

    # If model provided, try it first with common methods
    candidate_models = []
    if model:
        # strip leading 'models/' if present
        model_name = model.split('/')[-1]
        # try both with and without 'models/' qualifier
        candidate_models.append(model)
        candidate_models.append(model_name)
        candidate_models.append(f'models/{model_name}')

    # Start with provided api_base root(s)
    roots = [api_base.rstrip('/')]
    if not api_base.endswith('/v1') and not api_base.endswith('/v1beta'):
        roots.extend([api_base.rstrip('/') + '/v1', api_base.rstrip('/') + '/v1beta'])

    # Try provided model names first
    for root in roots:
        for m in candidate_models:
            for method in ('generateContent', 'generateText'):
                tried.append((root, m, method))
                out = try_model_method(root, m, method, 0)
                if out:
                    return out

    # If we reach here, attempt model discovery (ListModels) and pick a compatible model
    models_list = list_models()
    if not models_list:
        logger.warning('No models returned by ListModels; Gemini may not be enabled for this project or API base is incorrect.')
        return None

    # Normalize entries and attempt to pick a model that supports generateText or generateContent
    preferred = None
    for root, m_obj in models_list:
        # extract name and supported methods
        name = None
        supported = []
        if isinstance(m_obj, dict):
            name = m_obj.get('name') or m_obj.get('model') or m_obj.get('id')
            supported = m_obj.get('supportedMethods') or m_obj.get('availableMethods') or m_obj.get('methods') or []
        else:
            # unknown shape
            continue
        if not name:
            continue
        # If model matches requested fragment, prefer it
        if model and (model in name or name.endswith(model) or model.endswith(name)):
            # prefer generateText over generateContent if both present
            if 'generateText' in supported:
                preferred = (root, name, 'generateText')
                break
            if 'generateContent' in supported:
                preferred = (root, name, 'generateContent')
                break
        # otherwise prefer text-bison or gemini family heuristically
        if not preferred and ('text-bison' in name or 'bison' in name):
            preferred = (root, name, 'generateText')

    if not preferred and models_list:
        # as fallback pick the first model and method we can
        root, m_obj = models_list[0]
        name = m_obj.get('name') if isinstance(m_obj, dict) else None
        methods = m_obj.get('supportedMethods') if isinstance(m_obj, dict) else []
        method = 'generateText' if 'generateText' in (methods or []) else ('generateContent' if 'generateContent' in (methods or []) else 'generateText')
        preferred = (root, name or model, method)

    if preferred:
        root, name, method = preferred
        logger.info('Using discovered Gemini model %s with method %s at root %s', name, method, root)
        out = try_model_method(root, name, method, 0)
        if out:
            return out
        logger.warning('Discovered model %s failed to generate output.', name)

    if last_exc:
        logger.warning('Gemini calls exhausted. Last exception: %s', last_exc)
    else:
        logger.warning('Gemini calls exhausted without a usable model/method.')
    return None



# -----------------------------
# QUESTION SUMMARIZER
# -----------------------------
def summarize_question_obj(question, notes_texts=None):
    """
    Generate concise, AI-powered keynotes for a Question object using Gemini or OpenAI.
    Fallbacks are built in, including heuristic generation if both fail.
    """
    notes_texts = notes_texts or []
    combined_notes = "\n".join(notes_texts).strip()

    prompt = f"""
    Summarize the essential concepts from these tutor notes related to the question below.
    Question: {question.question_text}
    Notes: {combined_notes}

    Provide a clear 2-3 sentence key summary with main ideas and answer points.
    """

    gemini_prompt = f"""
    Provide a complete, well-explained answer and concise summary for the following:
    Question: {question.question_text}
    Notes: {combined_notes}

    Respond clearly and begin with 'Answer:' followed by explanation and examples.
    """

    gemini_key = getattr(settings, 'GEMINI_API_KEY', None) or os.environ.get('GEMINI_API_KEY')
    gemini_token = getattr(settings, 'GEMINI_BEARER_TOKEN', None) or os.environ.get('GEMINI_BEARER_TOKEN')

    # --- Prefer Gemini ---
    if gemini_key or gemini_token:
        result = call_gemini(gemini_prompt)
        if result:
            return result
        logger.warning("Gemini configured but failed; falling back to OpenAI.")
        openai_result = call_openai(gemini_prompt)
        if openai_result:
            return "(Gemini failed — using OpenAI fallback)\n" + openai_result
    else:
        return "⚠️ AI not configured. Please set GEMINI_API_KEY or GEMINI_BEARER_TOKEN and GEMINI_MODEL_NAME."

    # --- Heuristic fallback ---
    try:
        opts = list(question.options.all())
    except Exception:
        opts = []

    if opts:
        correct = [o.option_text for o in opts if getattr(o, 'is_correct', False)]
        if correct:
            return f"Answer: {' / '.join(correct)}. Explanation: Based on provided correct options."

    if combined_notes:
        sentences = re.split(r'(?<=[.!?])\s+', combined_notes)
        if sentences:
            q_words = set(re.findall(r'\w+', question.question_text.lower()))
            best_sentence = max(sentences, key=lambda s: len(set(re.findall(r'\w+', s.lower())) & q_words))
            return f"Answer: {best_sentence.strip()}. Explanation: Extracted from tutor notes."

    # --- Last resort fallback ---
    short_q = question.question_text[:150] + "..." if len(question.question_text) > 150 else question.question_text
    return f"Answer: {short_q}. Explanation: No AI response or notes available — fallback summary."
