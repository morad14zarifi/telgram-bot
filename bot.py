package bot;

import org.telegram.telegrambots.bots.TelegramLongPollingBot;
import org.telegram.telegrambots.meta.api.methods.send.SendMessage;
import org.telegram.telegrambots.meta.api.objects.Update;
import org.telegram.telegrambots.meta.exceptions.TelegramApiException;

import java.util.List;

public class GomalBot extends TelegramLongPollingBot {

    private final String username;
    private final Database database;

    // فروش هر چوب بستنی
    private static final int STICK_SELL_PRICE = 10;

    // پنج دقیقه
    private static final long GOGO_COOLDOWN = 5 * 60 * 1000L;

    public GomalBot(String token, String username) {

        super(token);

        this.username = username;
        this.database = new Database();
    }

    @Override
    public String getBotUsername() {
        return username;
    }

    @Override
    public void onUpdateReceived(Update update) {

        if (!update.hasMessage()) {
            return;
        }

        if (!update.getMessage().hasText()) {
            return;
        }

        String text =
                update.getMessage().getText().trim();

        long userId =
                update.getMessage()
                        .getFrom()
                        .getId();

        String name =
                update.getMessage()
                        .getFrom()
                        .getFirstName();

        long chatId =
                update.getMessage()
                        .getChatId();

        User user =
                database.getUser(userId, name);

        String lower =
                text.toLowerCase();

        if (lower.equals("گو گو")) {

            handleGogo(chatId, user);
            return;
        }

        if (lower.equals("رتبه")) {

            sendRanking(chatId);
            return;
        }

        if (lower.equals("پروفایل")) {

            sendProfile(chatId, user);
            return;
        }

        if (lower.equals("چوب بستنی")) {

            sendStickMenu(chatId, user);
            return;
        }

        if (lower.equals("دادن به گمال")) {

            feedGomal(chatId, user);
            return;
        }

        if (lower.equals("فروختن")) {

            sellStick(chatId, user);
            return;
        }

        if (lower.equals("/start")) {

            send(
                    chatId,
                    "🐫 به ربات گمال خوش اومدی!\n\n" +
                    "🐫 گو گو\n" +
                    "🏆 رتبه\n" +
                    "👤 پروفایل\n" +
                    "🍭 چوب بستنی"
            );
        }
    }

    private void handleGogo(long chatId, User user) {

        long now = System.currentTimeMillis();

        long difference =
                now - user.getLastGogo();

        if (difference < GOGO_COOLDOWN) {

            long remaining =
                    (GOGO_COOLDOWN - difference) / 1000;

            long minutes = remaining / 60;
            long seconds = remaining % 60;

            send(
                    chatId,
                    "⏳ هنوز وقتش نشده!\n" +
                    "دوباره بعد از " +
                    minutes + " دقیقه و " +
                    seconds + " ثانیه امتحان کن."
            );

            return;
        }

        user.setLastGogo(now);

        user.addPoint();

        int oldLevel =
                user.getLevel();

        user.addGogo();

        int newLevel =
                user.getLevel();

        database.save();

        String message =
                "🐫 گوووووو گو!\n\n" +
                "💰 +1 گمال پوینت\n" +
                "⭐ گمال پوینت: " +
                user.getPoints() + "\n" +
                "🔥 گو گو: " +
                user.getGogoCount() + "\n" +
                "🏅 لول: " +
                user.getLevel();

        if (newLevel > oldLevel) {

            message +=
                    "\n\n🎉 لول آپ!\n" +
                    "🏅 رسیدی به لول " +
                    newLevel + "!";

            if (newLevel == 2) {

                message +=
                        "\n🍭 یک چوب بستنی جایزه گرفتی!";
            }
        }

        send(chatId, message);
    }

    private void sendProfile(long chatId, User user) {

        send(
                chatId,
                "👤 پروفایل گمال\n\n" +
                "👤 " + user.getName() + "\n" +
                "🏅 لول: " + user.getLevel() + "\n" +
                "💰 گمال پوینت: " + user.getPoints() + "\n" +
                "🐫 تعداد گو گو: " + user.getGogoCount() + "\n" +
                "🍭 چوب بستنی: " + user.getIceCreamSticks() + "\n" +
                "❤️ شکم گمال: " +
                user.getStomach() + "/5"
        );
    }

    private void sendStickMenu(long chatId, User user) {

        if (user.getLevel() < 2) {

            send(
                    chatId,
                    "🔒 چوب بستنی از لول ۲ باز میشه!\n" +
                    "📈 هنوز " +
                    ((5 - (user.getGogoCount() % 5))) +
                    " گو گو تا لول بعدی مونده."
            );

            return;
        }

        send(
                chatId,
                "🍭 چوب بستنی\n\n" +
                "تعداد: " +
                user.getIceCreamSticks() + "\n\n" +
                "🐶 دادن به گمال\n" +
                "💰 فروختن\n\n" +
                "هر چوب بستنی ۲/۵ شکم گمال رو پر می‌کنه."
        );
    }

    private void feedGomal(long chatId, User user) {

        if (user.getLevel() < 2) {

            send(
                    chatId,
                    "🔒 این قابلیت از لول ۲ باز میشه."
            );

            return;
        }

        if (user.getIceCreamSticks() <= 0) {

            send(
                    chatId,
                    "🍭 چوب بستنی نداری!"
            );

            return;
        }

        if (user.getStomach() >= 5) {

            send(
                    chatId,
                    "🐶 شکم گمال پره!\n❤️ " +
                    user.getStomach() + "/5"
            );

            return;
        }

        user.useStick();

        database.save();

        send(
                chatId,
                "🐶 گمال چوب بستنی رو خورد!\n\n" +
                "🍭 -1 چوب بستنی\n" +
                "❤️ شکم گمال: " +
                user.getStomach() + "/5"
        );
    }

    private void sellStick(long chatId, User user) {

        if (user.getLevel() < 3) {

            send(
                    chatId,
                    "🔒 فروش چوب بستنی از لول ۳ باز میشه!"
            );

            return;
        }

        if (user.getIceCreamSticks() <= 0) {

            send(
                    chatId,
                    "🍭 چوب بستنی برای فروش نداری."
            );

            return;
        }

        user.sellStick();

        user.addPoint();

        for (int i = 1; i < STICK_SELL_PRICE; i++) {
            user.addPoint();
        }

        database.save();

        send(
                chatId,
                "💰 چوب بستنی فروخته شد!\n\n" +
                "🍭 -1 چوب بستنی\n" +
                "💰 +" + STICK_SELL_PRICE +
                " گمال پوینت"
        );
    }

    private void sendRanking(long chatId) {

        List<User> ranking =
                database.getRanking();

        if (ranking.isEmpty()) {

            send(
                    chatId,
                    "🏆 هنوز کسی امتیازی نگرفته!"
            );

            return;
        }

        StringBuilder text =
                new StringBuilder();

        text.append("🏆 رتبه‌بندی گمال‌ها\n\n");

        int limit =
                Math.min(10, ranking.size());

        for (int i = 0; i < limit; i++) {

            User user = ranking.get(i);

            String medal;

            if (i == 0) {
                medal = "🥇";
            } else if (i == 1) {
                medal = "🥈";
            } else if (i == 2) {
                medal = "🥉";
            } else {
                medal = "▫️";
            }

            text.append(
                    medal + " " +
                    (i + 1) + ". " +
                    user.getName() +
                    " — " +
                    user.getPoints() +
                    " پوینت\n"
            );
        }

        send(chatId, text.toString());
    }

    private void send(long chatId, String text) {

        SendMessage message =
                new SendMessage();

        message.setChatId(String.valueOf(chatId));
        message.setText(text);

        try {

            execute(message);

        } catch (TelegramApiException e) {

            e.printStackTrace();
        }
    }
}
