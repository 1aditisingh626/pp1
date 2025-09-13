# app.py
import streamlit as st
import pandas as pd
from textblob import TextBlob
import plotly.express as px
from supabase import create_client

# ---------- Supabase Connection ----------
SUPABASE_URL = "https://jijdfcpqrhbrmcujghkv.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImppamRmY3Bxcmhicm1jdWpnaGt2Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTc3MzE5MjUsImV4cCI6MjA3MzMwNzkyNX0.VaFeZXi1F8udHCuwGov4XIYCrTOY6fxrxOJFUn6I3SA"  # Replace with your anon/public key
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


# ---------- Helpers ----------
def read_tables():
    users_data = supabase.table("users").select("*").execute().data
    products_data = supabase.table("products").select("*").execute().data
    vendors_data = supabase.table("vendors").select("*").execute().data
    users = pd.DataFrame(users_data)
    products = pd.DataFrame(products_data)
    vendors = pd.DataFrame(vendors_data)
    return users, products, vendors


def analyze_sentiment(text):
    if not text:
        return None
    polarity = TextBlob(text).sentiment.polarity
    if polarity > 0.2:
        return "Positive"
    elif polarity < -0.2:
        return "Negative"
    else:
        return "Neutral"


def detect_priority(text):
    if not text: return "Medium"
    keywords = ["poison", "expired", "harm", "unsafe", "illness", "contaminated"]
    for word in keywords:
        if word in text.lower():
            return "High"
    return "Medium"


def compute_vendor_trust(vendor_id):
    if vendor_id is None:
        return 0, 0, 0  # if vendor_id is missing, return zeros

    # Fetch ratings safely
    try:
        ratings_data = (
            supabase.table("users")
            .select("rating")
            .eq("vendor_id", vendor_id)
            .is_neq("rating", None)  # safer None check
            .execute()
            .data
        )
    except Exception as e:
        print("Error fetching ratings:", e)
        ratings_data = []

    if ratings_data:
        ratings = [r["rating"] for r in ratings_data if r["rating"] is not None]
        avg_rating = sum(ratings)/len(ratings) if ratings else 0
    else:
        avg_rating = 0

    trust = round(avg_rating / 5 * 100, 2)

    # Resolved complaints
    try:
        complaints_data = (
            supabase.table("users")
            .select("complaint_status")
            .eq("vendor_id", vendor_id)
            .execute()
            .data
        )
    except Exception as e:
        print("Error fetching complaints:", e)
        complaints_data = []

    if complaints_data:
        resolved = sum(1 for c in complaints_data if str(c.get("complaint_status")).lower() == "resolved")
        resolved_ratio = round(resolved / len(complaints_data) * 100, 2)
    else:
        resolved_ratio = 0

    return trust, avg_rating, resolved_ratio



# ---------- Pages ----------
def page_home(users, products, vendors):
    st.markdown(
        "<h1 style='text-align:center; color:#2C3E50;'>🏷️ Product Quality Platform</h1>",
        unsafe_allow_html=True
    )
    st.markdown(
        "<h3 style='text-align:center; color:#16A085;'>Submit complaints • Track status • Vendor insights</h3>",
        unsafe_allow_html=True
    )

    # ---------- KPIs ----------
    total_complaints = users['complaint_text'].notna().sum()
    resolved_complaints = users[users['complaint_text'].notna()]['complaint_status'].str.lower().eq('resolved').sum()
    pending_complaints = total_complaints - resolved_complaints
    avg_rating = round(users['rating'].dropna().mean(), 2) if not users['rating'].dropna().empty else 0
    high_priority = users['complaint_priority'].str.lower().eq(
        'high').sum() if 'complaint_priority' in users.columns else 0

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total Complaints", total_complaints)
    col2.metric("Resolved", resolved_complaints)
    col3.metric("Pending", pending_complaints)
    col4.metric("Avg. Rating", avg_rating)
    col5.metric("High Priority", high_priority)

    st.markdown("---")

    # ---------- About Section ----------
    st.subheader("About This Platform")
    st.markdown("""
    The **Product Quality Platform** helps consumers submit complaints about products, track their status, 
    and get insights about vendors. Our goal is to ensure transparency and maintain high-quality standards 
    across products and vendors.  

    **Key Features:**  
    - Submit and track complaints easily  
    - Get vendor trust scores and analytics  
    - Multilingual support  
    - Power BI integration for advanced dashboards  
    - Real-time KPIs to monitor product quality trends
    """)

    st.markdown("---")

    # Optional: Add small charts or trend indicators
    st.subheader("Quick Insights")
    top_products = users.merge(products[['product_id', 'product_name']], on='product_id', how='left')
    top_products = top_products['product_name'].value_counts().head(5)
    st.bar_chart(top_products)

    top_vendors = users.merge(vendors[['vendor_id', 'vendor_name']], on='vendor_id', how='left')
    top_vendors = top_vendors['vendor_name'].value_counts().head(5)
    st.bar_chart(top_vendors)


# ---------- Submit Complaint Page ----------
import uuid
from datetime import datetime


def page_submit_complaint(users, products, vendors):
    st.header("📝 Submit Complaint")
    st.markdown("Fill in the details below to submit a product complaint. Fields marked * are required.")

    # Generate unique user_id automatically
    user_id = str(uuid.uuid4())[:8]  # 8-char unique ID
    st.text(f"Your User ID (auto-generated): {user_id}")

    name = st.text_input("Name *")
    email = st.text_input("Email *")
    state = st.text_input("State")

    product = st.selectbox("Select Product *", products['product_name'].tolist())
    vendor = st.selectbox("Select Vendor *", vendors['vendor_name'].tolist())
    complaint_text = st.text_area("Complaint Details *")
    rating = st.slider("Rating (1-5)", 1, 5, 3)
    complaint_image_url = st.text_input("Optional: Image URL")

    if st.button("Submit Complaint"):
        # Basic validation
        if not name or not email or not complaint_text:
            st.error("Please fill all required fields (*)")
            return

        # Auto detect priority and sentiment
        complaint_text_safe = complaint_text or ""
        priority = detect_priority(complaint_text_safe)
        sentiment = analyze_sentiment(complaint_text_safe)

        # Date in string format (JSON serializable)
        complaint_date = datetime.today().strftime("%Y-%m-%d")

        # Get product_id and vendor_id
        product_id = products.loc[products['product_name'] == product, 'product_id'].values[0]
        vendor_id = vendors.loc[vendors['vendor_name'] == vendor, 'vendor_id'].values[0]

        # Prepare data dictionary
        data_to_insert = {
            "user_id": user_id,
            "name": name,
            "email": email,
            "state": state,
            "product_id": product_id,
            "vendor_id": vendor_id,
            "complaint_text": complaint_text,
            "complaint_status": "Pending",
            "complaint_priority": priority,
            "rating": rating,
            "review_sentiment": sentiment,
            "complaint_date": complaint_date,
            "complaint_image_url": complaint_image_url
        }

        # Insert with error handling
        try:
            supabase.table("users").insert(data_to_insert).execute()
            st.success("✅ Complaint submitted successfully!")

            # Display KPIs immediately
            st.subheader("Your Complaint Summary")
            st.write(f"**Product:** {product}")
            st.write(f"**Vendor:** {vendor}")
            st.write(f"**Priority:** {priority}")
            st.write(f"**Sentiment:** {sentiment}")
            st.write(f"**Rating:** {rating}")
            st.write(f"**Status:** Pending")
            if complaint_image_url:
                st.image(complaint_image_url, caption="Attached Image", use_column_width=True)
        except Exception as e:
            st.error(f"Error submitting complaint: {e}")
            st.warning("Check if this email is already used or try again later.")


def page_track_complaints(users, products, vendors):
    st.header("📍 Track Your Complaints")
    st.markdown("Enter your User ID to see the status of all your complaints, insights, and suggestions.")

    user_id = st.text_input("Your User ID")

    if st.button("Track"):
        data = supabase.table("users").select("*").eq("user_id", user_id).execute().data
        df = pd.DataFrame(data)

        if df.empty:
            st.warning("No complaints found for this user. Make sure you entered the correct User ID.")
        else:
            # Merge with products and vendors for names
            df = df.merge(products[['product_id', 'product_name']], on='product_id', how='left')
            df = df.merge(vendors[['vendor_id', 'vendor_name']], on='vendor_id', how='left')

            # Prepare display dataframe
            df_display = df[['product_name', 'vendor_name', 'complaint_text', 'complaint_status',
                             'complaint_priority', 'review_sentiment', 'rating']].copy()
            df_display.rename(columns={'complaint_priority': 'priority', 'review_sentiment': 'sentiment'}, inplace=True)

            st.subheader("📋 Your Complaints")
            st.dataframe(df_display)

            st.markdown("---")
            st.subheader("💡 Insights")

            # Insights
            total_complaints = len(df_display)
            resolved = len(df_display[df_display['complaint_status'].str.lower() == 'resolved'])
            pending = len(df_display[df_display['complaint_status'].str.lower() == 'pending'])
            high_priority = len(df_display[df_display['priority'] == 'High'])
            positive_reviews = len(df_display[df_display['sentiment'] == 'Positive'])
            negative_reviews = len(df_display[df_display['sentiment'] == 'Negative'])
            neutral_reviews = len(df_display[df_display['sentiment'] == 'Neutral'])

            col1, col2, col3 = st.columns(3)
            col1.metric("Total Complaints", total_complaints)
            col2.metric("Resolved", resolved)
            col3.metric("Pending", pending)

            col4, col5, col6 = st.columns(3)
            col4.metric("High Priority", high_priority)
            col5.metric("Positive Reviews", positive_reviews)
            col6.metric("Negative Reviews", negative_reviews)

            st.write(f"Neutral Reviews: {neutral_reviews}")

            st.markdown("---")
            st.markdown(
                "**Tip:** Keep your complaint descriptions clear and detailed. High-priority issues like expired or contaminated products are flagged automatically.")


def page_vendor_dashboard(users, products, vendors):
    st.header("🏭 Vendor Dashboard")
    vendor_name = st.selectbox("Select Vendor", vendors['vendor_name'].tolist())
    vendor_id = vendors.loc[vendors['vendor_name']==vendor_name, 'vendor_id'].values[0]
    trust, avg_rating, resolved_pct = compute_vendor_trust(vendor_id)

    col1, col2, col3 = st.columns(3)
    col1.metric("🛡️ Trust Score", f"{trust}%")
    col2.metric("⭐ Average Rating", round(avg_rating,2))
    col3.metric("📄 Resolved %", f"{resolved_pct}%")

    # Insights
    st.subheader("🔍 Vendor Insights")
    v_complaints = users[users['vendor_id']==vendor_id]
    st.write(f"Total Complaints: {len(v_complaints)}")
    st.write(f"High Priority: {len(v_complaints[v_complaints['complaint_priority']=='High'])}")
    st.write(f"Positive Feedback: {len(v_complaints[v_complaints['review_sentiment']=='Positive'])}")



def page_analytics(users, products, vendors):
    st.header("📊 Analytics Dashboard")

    # Merge necessary tables
    df = users.merge(products[['product_id', 'product_name']], on='product_id', how='left')
    df = df.merge(vendors[['vendor_id', 'vendor_name']], on='vendor_id', how='left')
    df['complaint_priority'] = df['complaint_priority'].fillna("Medium")
    df['review_sentiment'] = df['review_sentiment'].fillna("Neutral")
    df['complaint_date'] = pd.to_datetime(df['complaint_date'], errors='coerce')

    # 1️⃣ Complaints by Product
    st.subheader("Top 10 Products by Complaints")
    top_products = df['product_name'].value_counts().head(10)
    fig1 = px.bar(x=top_products.index, y=top_products.values, labels={'x':'Product','y':'Complaints'}, title="Top Products")
    st.plotly_chart(fig1, use_container_width=True)

    # 2️⃣ Complaints by Vendor
    st.subheader("Top 10 Vendors by Complaints")
    top_vendors = df['vendor_name'].value_counts().head(10)
    fig2 = px.bar(x=top_vendors.index, y=top_vendors.values, labels={'x':'Vendor','y':'Complaints'}, title="Top Vendors")
    st.plotly_chart(fig2, use_container_width=True)

    # 3️⃣ Complaint Priority Distribution
    st.subheader("Complaint Priority Distribution")
    priority_counts = df['complaint_priority'].value_counts()
    fig3 = px.pie(values=priority_counts.values, names=priority_counts.index, title="Priority Distribution")
    st.plotly_chart(fig3, use_container_width=True)

    # 4️⃣ Sentiment Distribution
    st.subheader("User Sentiment Distribution")
    sentiment_counts = df['review_sentiment'].value_counts()
    fig4 = px.pie(values=sentiment_counts.values, names=sentiment_counts.index, title="Sentiment Distribution")
    st.plotly_chart(fig4, use_container_width=True)

    # 5️⃣ Complaints Over Time
    st.subheader("Complaints Over Time")
    complaints_time = df.groupby('complaint_date').size().reset_index(name='count')
    complaints_time = complaints_time.sort_values('complaint_date')
    fig5 = px.line(complaints_time, x='complaint_date', y='count', title="Complaints Over Time")
    st.plotly_chart(fig5, use_container_width=True)


def page_chatbot(users, products, vendors):

    st.header("💬 Multilingual Chatbot")
    st.markdown("Ask questions about submitting complaints, tracking status, or vendor info.")

    # Quick stats
    st.subheader("📊 Quick Stats")
    total_complaints = users['complaint_text'].notna().sum()
    resolved_complaints = users[users['complaint_status'].str.lower() == 'resolved'].shape[0]
    pending_complaints = users[users['complaint_status'].str.lower() == 'pending'].shape[0]
    total_products = products.shape[0]
    total_vendors = vendors.shape[0]

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total Complaints", total_complaints)
    col2.metric("Resolved", resolved_complaints)
    col3.metric("Pending", pending_complaints)
    col4.metric("Total Products", total_products)
    col5.metric("Total Vendors", total_vendors)

    # Language selection
    st.subheader("Select Language / भाषा")
    lang = st.radio("", ["English (en)", "Hindi (hi)"], horizontal=True)
    lang_code = "en" if lang.startswith("English") else "hi"

    # FAQ dictionary
    faqs = {
        "en": {
            "What is this platform?": "This is a complaint management and analytics platform for product quality.",
            "How do I submit a complaint?": "Go to the Submit Complaint page in the sidebar and fill in your complaint details.",
            "Can I track my complaint?": "Yes, use the Track Complaints page to see the status.",
            "Show quick stats": "The quick stats show total complaints, resolved/pending complaints, products, and vendors.",
            "How to see vendor info?": "Go to the Vendor Dashboard page to check trust scores and complaint resolution."
        },
        "hi": {
            "यह प्लेटफ़ॉर्म क्या है?": "यह उत्पाद गुणवत्ता के लिए शिकायत प्रबंधन और विश्लेषण प्लेटफ़ॉर्म है।",
            "मैं शिकायत कैसे दर्ज करूँ?": "साइडबार में 'Submit Complaint' पेज पर जाएँ और अपनी शिकायत दर्ज करें।",
            "क्या मैं अपनी शिकायत देख सकता हूँ?": "हाँ, 'Track Complaints' पेज पर जाकर स्थिति देखें।",
            "तेज़ आँकड़े दिखाएँ": "Quick Stats में कुल शिकायतें, हल/अनसुलझी शिकायतें, उत्पाद और विक्रेता दिखाए जाते हैं।",
            "विक्रेता जानकारी कैसे देखें?": "'Vendor Dashboard' पेज पर जाएँ और भरोसेमंद स्कोर और शिकायत समाधान देखें।"
        }
    }

    # Display FAQ as clickable buttons
    st.subheader("FAQs / सामान्य प्रश्न")
    faq_list = list(faqs[lang_code].keys())
    for question in faq_list:
        if st.button(question):
            st.info(faqs[lang_code][question])

    # Manual question input
    st.subheader("Ask your question here:")
    user_question = st.text_input("")
    if st.button("Get Answer"):
        answer = faqs.get(lang_code, {}).get(user_question, "Sorry, I don't have an answer for this yet.")
        st.info(answer)


def page_powerbi_dashboard():
    st.header("📊 Power BI Dashboard Embed")
    st.markdown("""
    <p>Embed your Power BI report here using the 'Publish to Web' link or iframe.</p>
    <iframe width="100%" height="600" src="YOUR_POWERBI_EMBED_LINK_HERE" frameborder="0" allowFullScreen="true"></iframe>
    """, unsafe_allow_html=True)


def page_raw_data(users, products, vendors):
    st.header("🗃️ Raw Data")
    st.subheader("Users")
    st.dataframe(users)
    st.subheader("Products")
    st.dataframe(products)
    st.subheader("Vendors")
    st.dataframe(vendors)


# ---------- Main ----------
st.set_page_config(page_title="Product Quality Platform", layout="wide")
st.sidebar.title("Navigation")

users, products, vendors = read_tables()
page = st.sidebar.selectbox("Go to",
                            ["Home", "Submit Complaint", "Track Complaint", "Vendor Dashboard", "Analytics", "Chatbot",
                             "Raw Data", "Power BI Dashboard"])

if page == "Home":
    page_home(users, products, vendors)
elif page == "Submit Complaint":
    page_submit_complaint(users, products, vendors)
elif page == "Track Complaint":
    page_track_complaints(users, products, vendors)
elif page == "Vendor Dashboard":
    page_vendor_dashboard(users, products, vendors)
elif page == "Analytics":
    page_analytics(users, products, vendors)
elif page == "Chatbot":
    page_chatbot(users, products, vendors)  # ✅ correct
elif page == "Raw Data":
    page_raw_data(users, products, vendors)
elif page == "Power BI Dashboard":
    page_powerbi_dashboard()
