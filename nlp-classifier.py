#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Modular NLP classifier for articles using LMStudio.
This script provides functions that can be imported to classify articles
based on their titles using an NLP model.
Questions are loaded from an external file.
"""

import os
import json
import time
import re
import requests
from typing import Dict, List, Any, Optional, Tuple, Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configuration for LMStudio API
DEFAULT_LMSTUDIO_API_URL = "http://localhost:1234/v1/chat/completions"
DEFAULT_LMSTUDIO_HEADERS = {
    "Content-Type": "application/json"
}

def load_articles(filepath: str) -> List[Dict[Any, Any]]:
    """
    Loads articles from a JSON file.
    
    Args:
        filepath: Path to the JSON file with the articles.
        
    Returns:
        List of loaded articles.
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as file:
            articles = json.load(file)
            print(f"Loaded {len(articles)} articles from file {filepath}")
            return articles
    except Exception as e:
        print(f"Error loading articles: {str(e)}")
        return []

def load_questions(filepath: str) -> List[Dict[str, Any]]:
    """
    Loads classification questions from a JSON file.
    
    Args:
        filepath: Path to the JSON file with questions.
        
    Returns:
        List of questions with their properties.
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as file:
            questions = json.load(file)
            print(f"Loaded {len(questions)} questions from file {filepath}")
            return questions
    except Exception as e:
        print(f"Error loading questions: {str(e)}")
        return []

def format_prompt(title: str, questions: List[Dict[str, Any]]) -> str:
    """
    Formats a prompt for the NLP model using the article title and questions.
    
    Args:
        title: Article title to analyze.
        questions: List of questions to ask about the title.
        
    Returns:
        Formatted prompt string.
    """
    prompt = f"""Analyze this scientific title: "{title}"\n\n"""
    
    for i, question in enumerate(questions, 1):
        prompt += f"{i}. {question['text']}\n"
        prompt += f"RESPOND ONLY WITH: {question['response_format']}\n\n"
    
    prompt += """ATTENTION: You must respond ONLY with the requested values. DO NOT add additional explanations.
If the title does not explicitly mention what is asked, respond with the default negative value."""
    
    return prompt

def query_lmstudio(
    prompt: str, 
    max_retries: int = 3, 
    retry_delay: int = 5,
    api_url: str = DEFAULT_LMSTUDIO_API_URL,
    headers: Dict[str, str] = DEFAULT_LMSTUDIO_HEADERS
) -> Dict[str, Any]:
    """
    Sends a query to the local model in LMStudio and handles retries.
    
    Args:
        prompt: Query text for the model.
        max_retries: Maximum number of attempts if there are failures.
        retry_delay: Seconds to wait between retries.
        api_url: URL for the LMStudio API.
        headers: Headers for the API request.
        
    Returns:
        Model response as a dictionary.
    """
    # System message to be stricter about response format
    system_message = (
        "You are an automatic scientific text classification system. "
        "You must respond ONLY with the requested values, WITHOUT ADDING ANY EXPLANATION, "
        "COMMENT OR ADDITIONAL NOTE. Only respond with the exact value requested."
    )
    
    payload = {
        "messages": [
            {"role": "system", "content": system_message},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.1,  # Low temperature for more deterministic responses
        "max_tokens": 50     # Reduced to avoid long responses
    }
    
    # Configure an extended timeout (3 minutes)
    timeout = 180
    
    for attempt in range(max_retries):
        try:
            print(f"Sending query to LMStudio (attempt {attempt+1}/{max_retries}, timeout: {timeout}s)...")
            
            response = requests.post(
                api_url,
                headers=headers,
                json=payload,
                timeout=timeout  # Extended timeout to give time to process
            )
            
            if response.status_code == 200:
                response_data = response.json()
                # Verify if the response has the expected format
                if "choices" in response_data and len(response_data["choices"]) > 0:
                    return response_data
                else:
                    print(f"Response with unexpected format: {response_data}")
                    if attempt < max_retries - 1:
                        print(f"Waiting {retry_delay} seconds before retrying...")
                        time.sleep(retry_delay)
                        retry_delay *= 2
            else:
                print(f"Attempt {attempt+1}/{max_retries} failed with code {response.status_code}")
                print(f"Response: {response.text}")
                if attempt < max_retries - 1:
                    print(f"Waiting {retry_delay} seconds before retrying...")
                    time.sleep(retry_delay)
                    # Increase wait time exponentially
                    retry_delay *= 2
        except requests.exceptions.Timeout:
            print(f"Timeout reached after {timeout} seconds in attempt {attempt+1}/{max_retries}")
            if attempt < max_retries - 1:
                print(f"Increasing timeout and waiting {retry_delay} seconds before retrying...")
                timeout = int(timeout * 1.5)  # Increase timeout for next attempt
                time.sleep(retry_delay)
                retry_delay *= 2
        except requests.RequestException as e:
            print(f"Connection error in attempt {attempt+1}/{max_retries}: {str(e)}")
            if attempt < max_retries - 1:
                print(f"Waiting {retry_delay} seconds before retrying...")
                time.sleep(retry_delay)
                retry_delay *= 2
    
    # If we get here, all attempts failed
    print(f"Could not get a response after {max_retries} attempts")
    return {"error": "Could not connect to LMStudio"}

def extract_answers(
    response: Dict[str, Any], 
    questions: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Extracts the answers from the model's response.
    
    Args:
        response: Model response.
        questions: List of questions with expected answer formats.
        
    Returns:
        Dictionary with extracted answers.
    """
    if "error" in response:
        return {
            "classification_error": response["error"]
        }
    
    try:
        # Extract the text from the response
        text = response.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
        print(f"Complete model response: '{text}'")
        
        # Parse the response
        result = {}
        
        # Split by lines and analyze each one
        lines = text.split('\n')
        cleaned_lines = [line.strip() for line in lines if line.strip()]
        
        # Process each question and extract the corresponding answer
        for i, question in enumerate(questions):
            field_name = question["field_name"]
            expected_type = question["answer_type"]
            default_value = question.get("default_value")
            
            # Try to find the answer in the lines
            answer = None
            
            # If we have enough lines, try to get the answer from the corresponding line
            if i < len(cleaned_lines):
                answer = cleaned_lines[i]
            
            # Process answer based on expected type
            if expected_type == "int":
                # For integer answers, extract first digit (0 or 1 for binary questions)
                if answer and re.search(r'\d+', answer):
                    match = re.search(r'\d+', answer)
                    if match:
                        answer = int(match.group())
                else:
                    # Look for digits in the entire text if specific line extraction failed
                    match = re.search(r'\b[01]\b', text)
                    if match:
                        answer = int(match.group())
                    else:
                        answer = default_value
                        
            elif expected_type == "string":
                # For string answers, use as is
                if not answer or answer in ["0", "1"]:
                    # If line is just a number, it's probably from another question
                    # Look for the answer elsewhere in the text
                    answer = default_value
                    for line in cleaned_lines:
                        if line not in ["0", "1"]:
                            answer = line
                            break
            
            # Add to results with default if needed
            result[field_name] = answer if answer is not None else default_value
            
            # Log the extracted answer
            print(f"Extracted {field_name}: {result[field_name]}")
        
        return result
        
    except Exception as e:
        print(f"Error processing the response: {str(e)}")
        
        # Generate default response with error
        result = {question["field_name"]: question.get("default_value") for question in questions}
        result["classification_error"] = str(e)
        
        return result

def classify_article(
    article: Dict[Any, Any], 
    questions: List[Dict[str, Any]],
    article_idx: int, 
    total_articles: int,
    api_url: str = DEFAULT_LMSTUDIO_API_URL,
    headers: Dict[str, str] = DEFAULT_LMSTUDIO_HEADERS
) -> Dict[Any, Any]:
    """
    Classifies an article using the NLP model based on questions.
    
    Args:
        article: Dictionary with the article information.
        questions: Classification questions.
        article_idx: Article index (for tracking).
        total_articles: Total number of articles (for tracking).
        api_url: URL for the LMStudio API.
        headers: Headers for the API request.
        
    Returns:
        Updated article with classification.
    """
    title = article.get("title", "")
    
    print(f"Classifying article {article_idx+1}/{total_articles}: {title[:50]}...")
    
    # Format the prompt based on the questions
    prompt = format_prompt(title, questions)

    # Query the model
    try:
        response = query_lmstudio(prompt, api_url=api_url, headers=headers)
        classification = extract_answers(response, questions)
        
        # Update the article with the classification
        article.update(classification)
        
    except Exception as e:
        print(f"Error classifying article: {str(e)}")
        # Default values and error
        defaults = {question["field_name"]: question.get("default_value") for question in questions}
        defaults["classification_error"] = str(e)
        article.update(defaults)
    
    return article

def classify_articles_batch(
    articles: List[Dict[Any, Any]], 
    questions: List[Dict[str, Any]],
    batch_size: int = 5, 
    sequential: bool = False,
    api_url: str = DEFAULT_LMSTUDIO_API_URL,
    headers: Dict[str, str] = DEFAULT_LMSTUDIO_HEADERS,
    callback: Optional[Callable[[int, int], None]] = None
) -> List[Dict[Any, Any]]:
    """
    Classifies articles in batches to avoid overloading the API.
    
    Args:
        articles: List of articles to classify.
        questions: Classification questions.
        batch_size: Batch size for parallel processing.
        sequential: If True, processes articles sequentially instead of in parallel.
        api_url: URL for the LMStudio API.
        headers: Headers for the API request.
        callback: Optional callback function that receives (current, total) progress updates.
        
    Returns:
        List of classified articles.
    """
    total_articles = len(articles)
    classified_articles = []
    
    if sequential:
        print(f"Classifying {total_articles} articles sequentially...")
        for idx, article in enumerate(articles):
            try:
                result = classify_article(article, questions, idx, total_articles, api_url, headers)
                classified_articles.append(result)
                
                # Call the callback if provided
                if callback:
                    callback(idx + 1, total_articles)
                
                # Small pause between articles to give the system time
                if idx < total_articles - 1:
                    print(f"Progress: {idx+1}/{total_articles} articles processed. Waiting 2 seconds...")
                    time.sleep(2)
            except Exception as e:
                print(f"Error classifying article {idx+1}: {str(e)}")
                # Add the article with error to maintain data integrity
                defaults = {question["field_name"]: question.get("default_value") for question in questions}
                defaults["classification_error"] = str(e)
                article.update(defaults)
                classified_articles.append(article)
    else:
        print(f"Classifying {total_articles} articles in batches of {batch_size}...")
        
        # Process articles in batches
        for i in range(0, total_articles, batch_size):
            batch = articles[i:min(i+batch_size, total_articles)]
            batch_results = []
            
            with ThreadPoolExecutor(max_workers=batch_size) as executor:
                futures = {
                    executor.submit(
                        classify_article, 
                        article, 
                        questions, 
                        i+idx, 
                        total_articles,
                        api_url,
                        headers
                    ): idx 
                    for idx, article in enumerate(batch)
                }
                
                for future in as_completed(futures):
                    try:
                        result = future.result()
                        batch_results.append(result)
                        
                        # Update progress (count completed futures)
                        if callback:
                            completed = i + len([f for f in futures if f.done()])
                            callback(completed, total_articles)
                            
                    except Exception as e:
                        print(f"Error in parallel processing: {str(e)}")
                        # Find which article caused the error
                        for f, idx in futures.items():
                            if f == future:
                                error_article = batch[idx]
                                defaults = {question["field_name"]: question.get("default_value") for question in questions}
                                defaults["classification_error"] = str(e)
                                error_article.update(defaults)
                                batch_results.append(error_article)
                                break
            
            # Sort the batch results according to the original order
            try:
                batch_results.sort(key=lambda x: futures[next(f for f in futures if futures[f] == batch_results.index(x))])
            except Exception as e:
                print(f"Error sorting batch results: {str(e)}. Continuing without sorting...")
            
            classified_articles.extend(batch_results)
            
            # Pause between batches to avoid overload
            if i + batch_size < total_articles:
                print(f"Progress: {min(i+batch_size, total_articles)}/{total_articles} articles processed. Waiting 5 seconds...")
                time.sleep(5)  # Increased from 3 to 5 seconds to give more time
    
    return classified_articles

def save_results(articles: List[Dict[Any, Any]], filepath: str) -> None:
    """
    Saves the classified articles to a JSON file.
    
    Args:
        articles: List of classified articles.
        filepath: Path where to save the JSON file.
    """
    # Create the outputs folder if it doesn't exist
    os.makedirs(os.path.dirname(filepath) or "outputs", exist_ok=True)
    
    try:
        with open(filepath, 'w', encoding='utf-8') as file:
            json.dump(articles, file, ensure_ascii=False, indent=4)
        print(f"Results saved to {filepath}")
    except Exception as e:
        print(f"Error saving results: {str(e)}")

def generate_classification_summary(articles: List[Dict[Any, Any]], questions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generates a classification summary.
    
    Args:
        articles: List of classified articles.
        questions: Classification questions.
        
    Returns:
        Dictionary with classification statistics.
    """
    total = len(articles)
    summary = {"total_articles": total}
    
    # Generate summary statistics for each question
    for question in questions:
        field_name = question["field_name"]
        answer_type = question["answer_type"]
        
        if answer_type == "int":
            # For integer answers, count frequencies
            values = [a.get(field_name) for a in articles if a.get(field_name) is not None]
            counts = {}
            for value in set(values):
                count = values.count(value)
                counts[value] = {
                    "count": count,
                    "percentage": round(count / total * 100, 2) if total > 0 else 0
                }
            summary[field_name] = counts
            
        elif answer_type == "string":
            # For string answers, count frequencies
            values = [a.get(field_name) for a in articles if a.get(field_name) is not None]
            value_counts = {}
            for value in values:
                if value in value_counts:
                    value_counts[value] += 1
                else:
                    value_counts[value] = 1
            
            # Sort by frequency
            value_counts = {k: v for k, v in sorted(value_counts.items(), key=lambda item: item[1], reverse=True)}
            summary[field_name] = value_counts
    
    # Count classification errors
    error_count = sum(1 for a in articles if "classification_error" in a)
    summary["classification_errors"] = error_count
    
    return summary

def check_lmstudio_connection(api_url: str = DEFAULT_LMSTUDIO_API_URL) -> bool:
    """
    Checks if LMStudio can be connected to.
    
    Args:
        api_url: URL for the LMStudio API.
        
    Returns:
        True if connection is successful, False otherwise.
    """
    try:
        # Extract base URL (remove path components)
        base_url = "/".join(api_url.split("/")[:3])
        models_url = f"{base_url}/v1/models"
        
        # Send a simple request to check the connection
        response = requests.get(models_url, timeout=5)
        return response.status_code == 200
    except:
        return False

def classify_articles(
    input_file: str, 
    questions_file: str,
    output_file: str, 
    batch_size: int = 5, 
    sequential: bool = True, 
    limit: Optional[int] = None, 
    start_index: int = 0,
    api_url: str = DEFAULT_LMSTUDIO_API_URL,
    headers: Dict[str, str] = DEFAULT_LMSTUDIO_HEADERS,
    callback: Optional[Callable[[int, int], None]] = None
) -> Tuple[bool, Dict[str, Any]]:
    """
    Main function to classify articles and save results.
    
    Args:
        input_file: Path to the JSON file with the articles to classify.
        questions_file: Path to the JSON file with the classification questions.
        output_file: Path where to save the JSON file with the results.
        batch_size: Batch size for parallel processing.
        sequential: If True, processes articles sequentially instead of in parallel.
        limit: Optional limit of articles to process (useful for testing).
        start_index: Index from which to start processing.
        api_url: URL for the LMStudio API.
        headers: Headers for the API request.
        callback: Optional callback function that receives (current, total) progress updates.
        
    Returns:
        Tuple with (success status, summary dictionary)
    """
    print("Starting article classification...")
    print(f"Mode: {'Sequential' if sequential else 'Parallel'}")
    
    # Check connection to LMStudio
    if not check_lmstudio_connection(api_url):
        print(f"ERROR: Cannot connect to LMStudio at {api_url}")
        print("Make sure LMStudio is running and the API server is enabled.")
        return False, {"error": "Connection to LMStudio failed"}
    
    start_time = time.time()
    
    # Load questions
    questions = load_questions(questions_file)
    if not questions:
        print("No questions found for classification.")
        return False, {"error": "No questions loaded"}
    
    # Load articles
    articles = load_articles(input_file)
    if not articles:
        print("No articles found to classify.")
        return False, {"error": "No articles loaded"}
    
    # Apply limits if specified
    if start_index > 0:
        print(f"Starting from article {start_index+1}...")
        articles = articles[start_index:]
    
    if limit is not None and limit > 0:
        print(f"Limiting processing to {limit} articles...")
        articles = articles[:limit]
    
    # Classify articles
    classified_articles = classify_articles_batch(
        articles, 
        questions, 
        batch_size, 
        sequential, 
        api_url,
        headers,
        callback
    )
    
    # If we're continuing from an index, load previous results
    if start_index > 0:
        try:
            with open(output_file, 'r', encoding='utf-8') as file:
                previous_results = json.load(file)
                # Combine results
                all_results = previous_results[:start_index] + classified_articles
                classified_articles = all_results
                print(f"Combined {start_index} previous results with {len(articles)} new results.")
        except (FileNotFoundError, json.JSONDecodeError):
            print(f"No previous results found or the file is corrupt. Only the new results will be saved.")
            # Create a list with None for the articles that weren't processed
            placeholder_results = [None] * start_index
            classified_articles = placeholder_results + classified_articles
    
    # Save results
    save_results(classified_articles, output_file)
    
    # Save a backup just in case
    backup_file = output_file.replace('.json', '_backup.json')
    save_results(classified_articles, backup_file)
    
    # Generate and display summary only of the articles that were processed
    processed_articles = articles
    if start_index > 0:
        processed_articles = classified_articles[start_index:]
    
    summary = generate_classification_summary(processed_articles, questions)
    print("\nClassification summary (only articles processed in this run):")
    print(f"Total articles processed: {summary['total_articles']}")
    
    for question in questions:
        field_name = question["field_name"]
        if field_name in summary:
            print(f"\n{question['text']} statistics:")
            if question["answer_type"] == "int":
                for value, stats in summary[field_name].items():
                    print(f"  Value {value}: {stats['count']} articles ({stats['percentage']}%)")
            else:
                print("  Top responses:")
                for i, (value, count) in enumerate(list(summary[field_name].items())[:10]):
                    print(f"  {i+1}. {value}: {count} articles")
    
    print(f"\nClassification errors: {summary['classification_errors']}")
    
    end_time = time.time()
    print(f"\nTotal execution time: {end_time - start_time:.2f} seconds")
    
    return True, summary

# Example questions file format:
"""
[
    {
        "text": "Is it an application of AI/ML/DL to fisheries/aquaculture/marine resources?",
        "response_format": "1 or 0",
        "field_name": "is_ai_fishery_application",
        "answer_type": "int",
        "default_value": 0
    },
    {
        "text": "What specific model does the title mention?",
        "response_format": "the exact name of the mentioned model or \"Not mentioned\"",
        "field_name": "model_type",
        "answer_type": "string",
        "default_value": "Not mentioned"
    }
]
"""

# Command-line interface if run directly
if __name__ == "__main__":
    import argparse
    
    # Configure argument parser
    parser = argparse.ArgumentParser(description='Article classifier using LMStudio')
    parser.add_argument('--input', type=str, default="outputs/integrated_results.json", 
                        help='Path to the input JSON file (default: outputs/integrated_results.json)')
    parser.add_argument('--questions', type=str, default="questions.json", 
                        help='Path to the questions JSON file (default: questions.json)')
    parser.add_argument('--output', type=str, default="outputs/classified_results.json", 
                        help='Path where to save the results (default: outputs/classified_results.json)')
    parser.add_argument('--batch-size', type=int, default=5, 
                        help='Batch size for parallel processing (default: 5)')
    parser.add_argument('--sequential', action='store_true', 
                        help='Use sequential processing instead of parallel')
    parser.add_argument('--limit', type=int, default=None, 
                        help='Limit the number of articles to process (useful for testing)')
    parser.add_argument('--start-from', type=int, default=0, 
                        help='Index from which to start processing (to continue a previous run)')
    parser.add_argument('--api-url', type=str, default=DEFAULT_LMSTUDIO_API_URL,
                        help=f'URL for the LMStudio API (default: {DEFAULT_LMSTUDIO_API_URL})')
    
    args = parser.parse_args()
    
    # Display configuration
    print("\n===== CONFIGURATION =====")
    print(f"Input file: {args.input}")
    print(f"Questions file: {args.questions}")
    print(f"Output file: {args.output}")
    print(f"Batch size: {args.batch_size}")
    print(f"Mode: {'Sequential' if args.sequential else 'Parallel'}")
    print(f"API URL: {args.api_url}")
    if args.limit:
        print(f"Article limit: {args.limit}")
    if args.start_from > 0:
        print(f"Start from index: {args.start_from}")
    print("========================\n")
    
    # Simple progress callback for command line
    def progress_callback(current, total):
        print(f"Progress: {current}/{total} articles processed ({current/total*100:.1f}%)")
    
    # Run the processing
    success, summary = classify_articles(
        input_file=args.input,
        questions_file=args.questions,
        output_file=args.output,
        batch_size=args.batch_size,
        sequential=args.sequential,
        limit=args.limit,
        start_index=args.start_from,
        api_url=args.api_url,
        callback=progress_callback
    )
    
    if not success:
        parser.exit(1, f"Classification failed: {summary.get('error', 'Unknown error')}")