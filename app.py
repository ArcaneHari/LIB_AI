from flask import Flask, render_template, request, send_file,jsonify
import pandas as pd
import io
import google.generativeai as genai
import typing_extensions as typing
import google_play_scraper
import re
import ast
import pandas as pd
import json
import os
import sys
from google_play_scraper import search
app = Flask(__name__)

ak=os.getenv("GOOGLE_API_KEY")
@app.route("/", methods=["GET", "POST"])
def index():
    df_html = None
    app_id = None
    no_of_creatives = None

    if request.method == "POST":
        try:
            # Get inputs from the form
            app_id = request.form.get("app_id")
            no_of_creatives = int(request.form.get("no_of_creatives"))

            result = google_play_scraper.app(app_id,'en','us')
            app_name=result['title']
            app_category=result['categories'][0]['name']
            app_intro=result['description']

            def extract_keyterms(paragraph,n=6):
                genai.configure(api_key=ak)

                class kt(typing.TypedDict):
                    key_terms: list[str]

                model = genai.GenerativeModel("gemini-1.5-flash")
                result = model.generate_content(f"Extract {n} important key terms from the following paragraph {paragraph}",
                    generation_config=genai.GenerationConfig(
                        response_mime_type="application/json", response_schema=list[kt]
                    ),
                )
                return result.text

            """Gemini Wrapper"""

            text=extract_keyterms(app_intro,6)
            data = json.loads(text)
            key_terms = data[0]['key_terms']
            key_terms

            def title_desc_gen(app_name,app_category,key_terms,app_intro,n):
                genai.configure(api_key=ak)
                model = genai.GenerativeModel("gemini-1.5-flash")
                response = model.generate_content(f"""Generate {n} unique sets of app titles, app descriptions, and their corresponding AdStrength ratings for the app '{app_name}'. Ensure that:
                                    - Each generated ad copy has substantial variation while keeping the app name '{app_name}' clearly recognizable in all titles.
                                    - They follow Google's UAC guidelines.
                                    - Titles and descriptions follow best practices for achieving 'Excellent' or 'Good' AdStrength.
                                    - The app belongs to the '{app_category}' category.
                                    - Incorporate key terms: {key_terms}.
                                    - Reference the following app details for context: {app_intro}.

                                
                                    Return the output as four plain Python lists:
                                    1. Titles (Ensure all titles closely resemble '{app_name}' without unnecessary modifications)
                                    2. Descriptions
                                    3. AdStrength ratings
                                    4. Ad Scores (between 0-100)
                                    Ensure the output is returned in plain text format, without any additional formatting or explanations.""")
                data=response.text
                lists = re.findall(r'\[.*?\]',data, re.DOTALL)
                list1 = ast.literal_eval(lists[0])
                list2 = ast.literal_eval(lists[1])
                list3= ast.literal_eval(lists[2])
                list4= ast.literal_eval(lists[3])
                return list1,list2,list3,list4
            
            app_titles,app_desc,ad_strength,ad_score=title_desc_gen(app_name,app_category,key_terms,app_intro,no_of_creatives)
            max_len = max(len(app_titles), len(app_desc))
            app_titles += [None] * (max_len - len(app_titles))
            app_desc += [None] * (max_len - len(app_desc))
            df = pd.DataFrame({'Titles': app_titles, 'Description': app_desc,'Ad Strength':ad_strength,'Ad Score':ad_score})
            df_html = df.to_html(classes="border border-gray-300 w-full text-left table-auto", index=False)
            styled_df_html = f"""
                                <style>
                                    .border {{
                                        border-collapse: collapse;
                                    }}
                                    .border th, .border td {{
                                        border: 1px solid black; /* */
                                        padding: 8px; /* Optional: Add padding for better spacing */
                                    }}
                                </style>
                                {df_html}
                                    """
            df_html=styled_df_html

            global csv_data
            csv_data = io.BytesIO()
            df.to_csv(csv_data, index=False)
            csv_data.seek(0)
        except ValueError:
            df_html = "<p style='color:red;'>Invalid input. Please try again.</p>"

    return render_template("index5.html", df_html=df_html, app_id=app_id, no_of_creatives=no_of_creatives)

@app.route("/download")
def download():
    return send_file(csv_data, mimetype="text/csv", as_attachment=True, download_name="data.csv")

@app.route("/autocomplete", methods=["GET"])
def autocomplete():
    """Fetch app suggestions from Google Play Store"""
    query = request.args.get("q", "").strip().lower()

    if not query:
        return jsonify([])  

    try:
        results = search(query, lang="en", country="us", n_hits=5)
        suggestions = [{"id": app["appId"], "name": app["title"]} for app in results]

        return jsonify(suggestions)
    
    except Exception as e:
        print("Error fetching Play Store data:", e)
        return jsonify([])  # Return an empty list in case of error

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

