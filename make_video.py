
def gemini_request(url, payload):

    last_error = None

    for attempt in range(1, 6):

        try:
            response = requests.post(
                url,
                params={"key": API_KEY},
                json=payload,
                timeout=API_TIMEOUT
            )

            # Daily quota सकिएमा रोक्ने
            if response.status_code == 429:
                raise RuntimeError(
                    "Gemini quota exceeded. "
                    "API quota reset नभएसम्म पर्खनुहोस्।"
                )

            # Server व्यस्त भएमा पुनः प्रयास गर्ने
            if response.status_code in (408, 500, 502, 503, 504):
                last_error = (
                    f"Gemini temporary error: "
                    f"{response.status_code} "
                    f"{response.text[:300]}"
                )

                print(
                    f"Gemini retry {attempt}/5: {last_error}"
                )

                if attempt < 5:
                    wait_time = min(10 * (2 ** (attempt - 1)), 120)
                    print(f"{wait_time} seconds पर्खँदै...")
                    time.sleep(wait_time)

                continue

            if not response.ok:
                raise RuntimeError(
                    f"Gemini API Error {response.status_code}: "
                    f"{response.text[:1000]}"
                )

            return response.json()

        except requests.exceptions.Timeout as exc:
            last_error = str(exc)

        except requests.exceptions.ConnectionError as exc:
            last_error = str(exc)

        except RuntimeError:
            raise

        print(
            f"Gemini connection retry {attempt}/5:",
            str(last_error)[:300]
        )

        if attempt < 5:
            time.sleep(10 * (2 ** (attempt - 1)))

    raise RuntimeError(
        f"Gemini 5 पटक प्रयास गर्दा पनि सफल भएन: {last_error}"
    )
