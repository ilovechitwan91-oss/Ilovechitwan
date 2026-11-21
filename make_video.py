def gemini_request(url, payload):

    last_error = None

    for attempt in range(1, MAX_RETRIES + 1):

        try:
            response = requests.post(
                url,
                params={"key": API_KEY},
                json=payload,
                timeout=API_TIMEOUT
            )

            # Quota सकिएमा retry नगर्ने
            if response.status_code == 429:
                raise RuntimeError(
                    "Gemini daily quota exceeded. "
                    "Cruz voice quota सकियो।"
                )

            if response.status_code >= 500:
                raise RuntimeError(
                    f"Gemini server error: {response.status_code}"
                )

            if not response.ok:
                raise RuntimeError(
                    f"Gemini API Error {response.status_code}: "
                    f"{response.text[:1000]}"
                )

            return response.json()

        except requests.exceptions.Timeout as exc:
            last_error = exc

        except requests.exceptions.ConnectionError as exc:
            last_error = exc

        except RuntimeError:
            raise

        print(
            f"Gemini retry {attempt}/{MAX_RETRIES}:",
            str(last_error)[:300]
        )

        if attempt < MAX_RETRIES:
            time.sleep(5 * (2 ** (attempt - 1)))

    raise RuntimeError(str(last_error))
