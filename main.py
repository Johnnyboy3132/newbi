import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler, CallbackQueryHandler, CallbackContext 
from telegram.constants import ParseMode
import pandas as pd
import os
# from crewai import Agent, Task, Crew, Process
from crewai.agent import Agent
from crewai.task import Task
from crewai.process import Process
from crewai.crew import Crew

from fiverr_api import session
import json

os.environ["OPENAI_API_BASE"] = 'https://api.groq.com/openai/v1'
os.environ["OPENAI_MODEL_NAME"] ='llama-3.1-8b-instant'  # Adjust based on available model
os.environ["OPENAI_API_KEY"] ='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'


# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)
EXCEL_FILE = 'data.xlsx'



# Define states
TASK, ASK_WHAT_EAT, URL, PROCESS_DATA, ASK_CORRECT, ASK_FEEDBACK = range(6)




def remove_keys(data, keys_to_remove):
    if isinstance(data, dict):
        # Use list(data.keys()) to avoid runtime error due to dictionary size change
        for key in list(data.keys()):
            if key in keys_to_remove:
                del data[key]
            else:
                remove_keys(data[key], keys_to_remove)
    elif isinstance(data, list):
        for item in data:
            remove_keys(item, keys_to_remove)

def AI(fiver_gig_url,task,business):
    session.set_scraper_api_key("4d5198ecf21aa959a962b011968e665e")
    response = session.get(fiver_gig_url) # your fiverr url should be here
    json_data = response.props_json() # gives you JSON
    # print(response.soup) # gives you beautiful soup instance
    # You can use `response.soup` to further extract your information.
    # print(json_data)
    # Load JSON data
    pretty = json.dumps(json_data, indent=4)
    data = json.loads(pretty)

    # Keys to remove
    keys_to_remove = ["gigId","gigStatus","categoryId","subCategoryId","nestedSubCategoryId","encryptedGigId","sellerId","isSellerBlocked","traffiqed","isSellerBlocked","gigVisibleToSeller","gigVisibleToBuyer","isTrustedUser","includeWorkSample","profilePhoto","awayReason","allowContact","awayMessage","endDate","memberSince","recentDelivery","hasProfilePhoto","translationKey","visibility","order","src","media","isWorkSample","itemScopeType","attachmentId","typeVideo","videoSrc","typeImage","filename","orderId","pages","typePdf","id","maxNumWordsPerOneMoreDay","maxNumWordsPerPackageDuration","included","value","extra","serviceId","type","calculators","customExtras","recurringOptions","gigCollectedCount","nextProjectIds","item","portfolioProjectsThumbs","photo_url","currentUserStatus","allowCustomOrders","status","otherGigs","gigIds","repeatScore","image","video","score","workflow","uid","liveSession","buyerReview","predefinedStepId","workProcess","instantOrderSettings","promotedGigs","has_next","gig_id","encrypted_order_id","is_business","seller_role_id","seller_img_url","filters_counters","introVideo","gigSellerTranslation","template","rollouts","dynamicTranslations","thumbnail","user_image_url","work_sample","work_sample_small","work_sample_content_type","work_sample_preview_url","work_sample_id"]

    # Remove specified keys
    remove_keys(data, keys_to_remove)

    benchmark_creator = Agent(
        role = "benchmark creator",
        goal = "accurately create a benchmark for people to find the perfect freelancer to outsource to. your answer should only include the benchmark criterias. Benchmark should be out of 100, 0 means this gig is not what I'm looking for, 100 means this is the perfect match. - Each branch of benchmark should only be true or false and adds up the score total at 100. for example 'does the gig include skill [skill] or not?' ",
        backstory = "You are an AI assistant to create benchmarks for people to find the freelancer they are looking for, your answer should only include the benchmark criterias. Benchmark should be out of 100, 0 means this gig is not what I'm looking for, 100 means this is the perfect match. - Each branch of benchmark should only be true or false and adds up the score total at 100. for example 'does the gig include skill [skill] or not?' ",
        verbose = True,
        allow_delegation = False,

    )

    benchmark_checker = Agent(
        role = "benchmark checker",
        goal = "Based on the benchmark given and all the informtions from the gig, score the gig with the benchmark and explain why you score it that way. At the end write summary and total score",
        backstory = "You are an AI assistant to score the given gig with given benchmark, alone the way you should explain why did you score it that way. At the end write summary and total score",
        verbose = True,
        allow_delegation = False,

    )

    create_benchmark = Task(
        description = f"Create an benchmark for the following: '{task}', and check if the freelancer have experience with the industry: {business}",
        agent = benchmark_creator,
        expected_output = "A benchmark"
    )

    score_gig = Task(
        description = f"Score the gig: '{data}' based on the benchmark provided by the 'benchmark creator' agent. and write a summary and total score at the end",
        agent = benchmark_checker,
        expected_output = "a list of score with detail explaination to the gig based on the benchmark provided by the 'benchmark creator' agent. write a sumary and total score at the end"
    )

    crew = Crew(
        agents = [benchmark_creator, benchmark_checker],
        tasks = [create_benchmark, score_gig],
        verbose = 2,
        process = Process.sequential
    )
    return crew.kickoff()


def save_data_to_excel(data):
    if os.path.exists(EXCEL_FILE):
        df = pd.read_excel(EXCEL_FILE)
    else:
        df = pd.DataFrame(columns=['User ID', 'Task', 'Business', 'Gig URL', 'Result', 'Score', 'Feedback'])

    new_data = pd.DataFrame({
        'User ID': [data['user_id']],
        'Task': [data['task']],
        'Business': [data['business']],
        'Gig URL': [data['url']],
        'Result': [data['result']],
        'Score': [data['score']],
        'Feedback': [data['feedback']]
    })

    df = pd.concat([df, new_data], ignore_index=True)
    df.to_excel(EXCEL_FILE, index=False)

# Define start handler
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    message = (
        "<b>Hi! I'm New-Bility AI that helps you check if the freelancer is what you are looking for.</b>\n\n"
        "I will need 3 information to analyze it for you! (Task, Your business, and gig url of freelancer)\n\n"
        "<i>Note: By starting this, you agree with giving all the chat history and your telegram contact to Newbility for product development purpose. (We'll not give your personal data to anyone outside of Newbility)</i>\n\n"
        "Let's start with first question! What is the task you wanted to outsource? please describe as detail as possible! you can take bottom info as example\n"
        "• <i>How long do you want the task to be delivered</i>\n"
        "• <i>What's your expectation of the quality?</i>\n"
        "• <i>is their past experience a must have or nice to have?</i>\n"
    )

    await update.message.reply_text(message, parse_mode=ParseMode.HTML)
    return TASK

# Define handlers for each state
async def ask_how_are_you(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['task'] = update.message.text
    
    message = (
        "<b>Understood, please describe your business as detail as possible, you can take below info as example:</b>\n\n"
        "• <i>What industry are you in?</i>\n"
        "• <i>What kind of service does your business provide?</i>\n"
        "• <i>Do you have anyone in the team have skill in the outsourced task?</i>\n"
    )

    await update.message.reply_text(message, parse_mode=ParseMode.HTML)
    return ASK_WHAT_EAT

async def ask_what_eat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['business'] = update.message.text
    await update.message.reply_text("Now, Please provide the freelancer's gig URL, and we'll be ready to go!")
    return URL

async def ask_linkedin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['url'] = update.message.text

    # Process the data
    data = context.user_data
    logger.info("Collected data: %s", data)

    # Create inline keyboard
    keyboard = [
        [
            InlineKeyboardButton("Yes", callback_data='yes'),
            InlineKeyboardButton("Fair enough", callback_data='fair'),
            InlineKeyboardButton("No", callback_data='no'),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    result = AI(data['url'],data['task'],data['business'])
    
    # Print out the data and ask for confirmation with buttons
    await update.message.reply_text(
        f"{result}\n\n"
        
        f"Is the result helping you?",
        reply_markup=reply_markup
    )
    context.user_data['result'] = ''
    return ASK_CORRECT

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    context.user_data['score'] = query.data
    await query.edit_message_text(text=f"You selected: {query.data}")
    await query.message.reply_text("Please give us some feedback so we can be better for you!")
    return ASK_FEEDBACK

async def ask_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['feedback'] = update.message.text
    context.user_data['user_id'] = update.message.from_user.id
    context.user_data['user_name'] = update.message.from_user.name

    # Store all the data in a dataset (for simplicity, we'll just log it)
    data = context.user_data
    logger.info("Final collected data: %s", data)
    save_data_to_excel(data)
    await update.message.reply_text("Thank you for testing our product. If you would like to test again, use /start !")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Conversation cancelled.")
    return ConversationHandler.END

# Define a keep-alive function
async def keep_alive(context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info('Keeping the bot alive...')

def main() -> None:
    """Run the bot."""
    application = Application.builder().token('6460591308:AAGpGyNVcmKuR9BPayGOTRkxZy2YBKbt68k').build()
    # Add a job to keep the bot alive

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            TASK: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_how_are_you)],
            ASK_WHAT_EAT: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_what_eat)],
            URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_linkedin)],
            ASK_CORRECT: [CallbackQueryHandler(button_callback)],
            ASK_FEEDBACK: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_feedback)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    application.add_handler(conv_handler)
    application.job_queue.run_repeating(keep_alive, interval=300, first=10)  # Keep alive every 5 minutes
    # Start the Bot
    application.run_polling()

if __name__ == '__main__':
    main()
