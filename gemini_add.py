    
    async def _call_gemini(
        self,
        messages: List[Dict[str, str]],
        temperature: float,
        max_tokens: int,
        model: str,
        stream: bool,
        **kwargs
    ) -> Dict[str, Any]:
        """Call Google Gemini API"""
        
        # Convert OpenAI message format to Gemini format
        system_instruction = None
        chat_messages = []
        
        for msg in messages:
            if msg["role"] == "system":
                system_instruction = msg["content"]
            elif msg["role"] == "user":
                chat_messages.append({"role": "user", "parts": [msg["content"]]})
            elif msg["role"] == "assistant":
                chat_messages.append({"role": "model", "parts": [msg["content"]]})
        
        # Configure generation
        generation_config = {
            "temperature": temperature,
            "max_output_tokens": max_tokens,
        }
        
        # Use GenerativeModel with system instruction if provided
        if system_instruction:
            model_instance = genai.GenerativeModel(
                model_name=model,
                system_instruction=system_instruction
            )
        else:
            model_instance = self.gemini_model
        
        # Generate response
        if stream:
            # Streaming not fully implemented yet
            response = await model_instance.generate_content_async(
                chat_messages,
                generation_config=generation_config,
                stream=False
            )
            return {"stream": response}
        else:
            response = await model_instance.generate_content_async(
                chat_messages,
                generation_config=generation_config
            )
        
        # Extract token counts (Gemini provides usage metadata)
        prompt_tokens = response.usage_metadata.prompt_token_count if hasattr(response, 'usage_metadata') else 0
        completion_tokens = response.usage_metadata.candidates_token_count if hasattr(response, 'usage_metadata') else 0
        
        return {
            "content": response.text,
            "model": model,
            "tokens_used": prompt_tokens + completion_tokens,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "finish_reason": "stop"  # Gemini doesn't provide detailed finish reasons in same format
        }


# Singleton instance
llm_router = LLMRouter()
