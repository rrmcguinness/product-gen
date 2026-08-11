import time
from google.genai.errors import APIError
from google.genai import Client, types
from .model import StepMetrics
from typing import Any, Tuple
import threading

rate_limit_lock = threading.Lock()
call_timestamps = []

def check_rate_limit():
    while True:
        with rate_limit_lock:
            now = time.time()
            global call_timestamps
            call_timestamps = [t for t in call_timestamps if now - t < 60]
            
            if len(call_timestamps) < 25:
                call_timestamps.append(now)
                return
                
            sleep_time = 60 - (now - call_timestamps[0])
            
        if sleep_time > 0:
            print(f"    [Rate Limiter] Hit limit (25/min). Sleeping for {sleep_time:.2f}s...")
            time.sleep(sleep_time)

class LLMError(Exception):
    def __init__(self, original_error: Exception, metrics: StepMetrics):
        self.original_error = original_error
        self.metrics = metrics
        super().__init__(f"LLM call failed: {original_error}")

def call_gemini(
    client: Client, 
    model: str, 
    contents: Any, 
    config: types.GenerateContentConfig, 
    step_name: str, 
    max_retries: int = 3
) -> Tuple[Any, StepMetrics]:
    """
    Wrapper to call Gemini models with unified error handling, retries, and metrics collection.
    """
    start_time = time.time()
    http_errors = {}
    retries = 0
    
    for attempt in range(max_retries + 1):
        try:
            if attempt > 0:
                print(f"    [Retrying] {step_name} (Attempt {attempt}/{max_retries})...")
            
            check_rate_limit()
            
            response = client.models.generate_content(
                model=model,
                contents=contents,
                config=config
            )
            
            end_time = time.time()
            
            usage = response.usage_metadata
            input_tokens = usage.prompt_token_count if usage and usage.prompt_token_count is not None else 0
            output_tokens = usage.candidates_token_count if usage and usage.candidates_token_count is not None else 0
            total_tokens = input_tokens + output_tokens
            
            metrics = StepMetrics(
                step_name=step_name,
                time_taken=end_time - start_time,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                model_used=model,
                retries=retries,
                http_errors=http_errors
            )
            return response, metrics
            
        except APIError as e:
            code = getattr(e, 'code', None) or getattr(e, 'status_code', None) or 0
            http_errors[code] = http_errors.get(code, 0) + 1
            print(f"    [Warning] {step_name} failed (API Error {code}): {e}")
            
            if attempt < max_retries:
                retries += 1
                delay = 2 ** attempt
                print(f"      Waiting {delay}s before retry...")
                time.sleep(delay)
            else:
                print(f"    [Error] Max retries reached for {step_name}.")
                end_time = time.time()
                metrics = StepMetrics(
                    step_name=f"{step_name} (Failed)",
                    time_taken=end_time - start_time,
                    model_used=model,
                    retries=retries,
                    http_errors=http_errors
                )
                raise LLMError(e, metrics)
                
        except Exception as e:
            http_errors[0] = http_errors.get(0, 0) + 1
            print(f"    [Warning] {step_name} unexpected error: {e}")
            
            if attempt < max_retries:
                retries += 1
                delay = 2 ** attempt
                print(f"      Waiting {delay}s before retry...")
                time.sleep(delay)
            else:
                print(f"    [Error] Max retries reached for {step_name}.")
                end_time = time.time()
                metrics = StepMetrics(
                    step_name=f"{step_name} (Failed)",
                    time_taken=end_time - start_time,
                    model_used=model,
                    retries=retries,
                    http_errors=http_errors
                )
                raise LLMError(e, metrics)
