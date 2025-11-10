import click
import asyncio
from groq import Groq
from config import settings


@click.command()
@click.argument('query')
@click.option('--temp', default=0.6, type=float, help='Temperature (0.0-1.0)')
@click.option('--debug', is_flag=True, help='Show debug info')
def ask(query: str, temp: float, debug: bool):
    if not settings.groq_api_key:
        print("\nERROR: GROQ_API_KEY not found in environment")
        print("Add it to your .env file:\n")
        print("GROQ_API_KEY=your_key_here\n")
        return

    print(f"\nDirect Groq Query (temp={temp})")
    print(f"Model: {settings.groq_model}")
    print(f"Question: {query}\n")

    async def main():
        prompt = f"""Answer this question.

User: {query}

Your response:"""

        try:
            client = Groq(api_key=settings.groq_api_key)
            
            print("Calling Groq API...\n")
            
            completion = await asyncio.to_thread(
                client.chat.completions.create,
                model=settings.groq_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=temp,
                max_tokens=settings.max_output_tokens,
            )
            
            answer = completion.choices[0].message.content.strip()

            print("="*60)
            print("ANSWER")
            print("="*60)
            print(answer)
            print("="*60 + "\n")
            
            if debug:
                print(f"Tokens used: {completion.usage.total_tokens}")
                print(f"Model: {completion.model}\n")

        except Exception as e:
            print(f"Groq API Error: {e}\n")
            if debug:
                import traceback
                traceback.print_exc()

    asyncio.run(main())


if __name__ == "__main__":
    ask()