#!/usr/bin/env python3
"""
T.O.I.B.O.T - Barcha funksiyalari to'liq jamlangan, xatolari tuzatilgan yagona fayl.
New repository uchun tayyor.
"""
import os
import shutil
import urllib.request
import zipfile

FILES = {
    ".github/workflows/build.yml": """name: Build T.O.I.B.O.T Android APK

on:
  push:
    branches: [ "main", "master" ]
  workflow_dispatch:

jobs:
  build-apk:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up JDK 17
        uses: actions/setup-java@v4
        with:
          distribution: 'temurin'
          java-version: '17'

      - name: Generate full T.O.I.B.O.T project and download offline STT model
        run: python3 TOIBOT_FULL_APP.py

      - name: Build APK with Gradle
        run: gradle assembleDebug --stacktrace

      - name: Upload TOIBOT APK artifact
        uses: actions/upload-artifact@v4
        with:
          name: TOIBOT-APK
          path: app/build/outputs/apk/debug/*.apk
          if-no-files-found: error
""",
    "settings.gradle.kts": """pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}
dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
        flatDir {
            dirs("app/libs")
        }
    }
}

rootProject.name = "ToibotAssistant"
include(":app")
""",
    "build.gradle.kts": """plugins {
    id("com.android.application") version "8.2.2" apply false
    id("org.jetbrains.kotlin.android") version "1.9.22" apply false
}
""",
    "gradle.properties": """org.gradle.jvmargs=-Xmx2048m -Dfile.encoding=UTF-8
android.useAndroidX=true
kotlin.code.style=official
""",
    "app/build.gradle.kts": """plugins {
    id("com.android.application")
    id("org.jetbrains.kotlin.android")
}

android {
    namespace = "com.example.toibot"
    compileSdk = 34

    defaultConfig {
        applicationId = "com.example.toibot"
        minSdk = 24
        targetSdk = 34
        versionCode = 1
        versionName = "5.0-toibot-complete"
    }

    buildTypes {
        release {
            isMinifyEnabled = false
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }
    kotlinOptions {
        jvmTarget = "17"
    }
    androidResources {
        noCompress += listOf("tflite", "onnx", "mdl", "ie", "mat", "stats", "dubm", "fst", "int")
    }
}

dependencies {
    implementation("androidx.core:core-ktx:1.12.0")
    implementation("androidx.appcompat:appcompat:1.6.1")
    implementation("com.alphacephei:vosk-android:0.3.47")
    implementation("net.java.dev.jna:jna:5.13.0@aar")
    implementation(fileTree(mapOf("dir" to "libs", "include" to listOf("*.aar"))))
}
""",
    "app/src/main/AndroidManifest.xml": """<?xml version="1.0" encoding="utf-8"?>
<manifest xmlns:android="http://schemas.android.com/apk/res/android">

    <uses-permission android:name="android.permission.RECORD_AUDIO" />
    <uses-permission android:name="android.permission.INTERNET" />
    <uses-permission android:name="android.permission.ACCESS_NETWORK_STATE" />
    <uses-permission android:name="android.permission.READ_CONTACTS" />
    <uses-permission android:name="android.permission.CALL_PHONE" />
    <uses-permission android:name="android.permission.SEND_SMS" />
    <uses-permission android:name="android.permission.SYSTEM_ALERT_WINDOW" />
    <uses-permission android:name="android.permission.FOREGROUND_SERVICE" />
    <uses-permission android:name="android.permission.FOREGROUND_SERVICE_MICROPHONE" />
    <uses-permission android:name="android.permission.CAMERA" />
    <uses-permission android:name="android.permission.VIBRATE" />
    <uses-permission android:name="android.permission.SET_ALARM" />

    <application
        android:allowBackup="true"
        android:label="T.O.I.B.O.T"
        android:supportsRtl="true"
        android:theme="@style/Theme.AppCompat.NoActionBar">

        <activity
            android:name=".MainActivity"
            android:exported="true">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>

        <service
            android:name=".ToibotForegroundService"
            android:enabled="true"
            android:exported="false"
            android:foregroundServiceType="microphone" />

        <service
            android:name=".ToibotAccessibilityService"
            android:exported="true"
            android:permission="android.permission.BIND_ACCESSIBILITY_SERVICE">
            <intent-filter>
                <action android:name="android.accessibilityservice.AccessibilityService" />
            </intent-filter>
            <meta-data
                android:name="android.accessibilityservice"
                android:resource="@xml/accessibility_service_config" />
        </service>

    </application>

</manifest>
""",
    "app/src/main/res/xml/accessibility_service_config.xml": """<?xml version="1.0" encoding="utf-8"?>
<accessibility-service xmlns:android="http://schemas.android.com/apk/res/android"
    android:accessibilityEventTypes="typeWindowStateChanged|typeWindowContentChanged"
    android:accessibilityFeedbackType="feedbackGeneric"
    android:canPerformGestures="true"
    android:canRetrieveWindowContent="true"
    android:canTakeScreenshot="true"
    android:notificationTimeout="100" />
""",
    "app/src/main/java/com/example/toibot/ToibotOrbView.kt": """package com.example.toibot

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.util.AttributeSet
import android.view.View
import kotlin.math.cos
import kotlin.math.sin

class ToibotOrbView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null
) : View(context, attrs) {

    enum class OrbState { IDLE, LISTENING, SPEAKING, CONFIRMING }

    var state: OrbState = OrbState.IDLE
        set(value) {
            field = value
            invalidate()
        }

    var audioAmplitude: Float = 0f
        set(value) {
            field = value.coerceIn(0f, 1f)
            invalidate()
        }

    private var phase = 0f

    private val corePaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.parseColor("#18B7A6")
        style = Paint.Style.FILL
    }

    private val dotPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.parseColor("#80FFF3")
        style = Paint.Style.FILL
    }

    private val ringPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.parseColor("#22D3EE")
        style = Paint.Style.STROKE
        strokeWidth = 3f
    }

    private val outerRingPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.parseColor("#0D9488")
        style = Paint.Style.STROKE
        strokeWidth = 2f
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        val cx = width / 2f
        val cy = height / 2f
        val baseRadius = minOf(cx, cy) * 0.42f

        val pulse = when (state) {
            OrbState.IDLE -> sin(phase) * 3f
            OrbState.LISTENING -> 6f + audioAmplitude * 16f + sin(phase * 2f) * 4f
            OrbState.SPEAKING -> 10f + audioAmplitude * 22f + sin(phase * 3f) * 6f
            OrbState.CONFIRMING -> 8f + sin(phase * 1.5f) * 5f
        }

        for (i in 1..3) {
            val r = baseRadius + i * 11f + pulse * (0.4f + i * 0.25f)
            outerRingPaint.alpha = (180 - i * 45).coerceIn(25, 200)
            canvas.drawCircle(cx, cy, r, outerRingPaint)
        }

        ringPaint.color = when (state) {
            OrbState.CONFIRMING -> Color.parseColor("#F59E0B")
            OrbState.SPEAKING -> Color.parseColor("#2DD4BF")
            else -> Color.parseColor("#14B8A6")
        }
        canvas.drawCircle(cx, cy, baseRadius + pulse * 0.6f, ringPaint)

        corePaint.alpha = 95
        canvas.drawCircle(cx, cy, baseRadius * 0.78f + pulse * 0.3f, corePaint)

        val dotRingR = baseRadius * 0.55f + pulse * 0.25f
        for (k in 0 until 16) {
            val angle = Math.toRadians((k * 22.5 + phase * 18.0))
            val dx = cx + cos(angle).toFloat() * dotRingR
            val dy = cy + sin(angle).toFloat() * dotRingR
            canvas.drawCircle(dx, dy, 2.5f, dotPaint)
        }

        phase += 0.08f
        postInvalidateOnAnimation()
    }
}
""",
    "app/src/main/java/com/example/toibot/ContactMatcher.kt": """package com.example.toibot

import android.content.Context
import android.provider.ContactsContract

data class MatchedContact(
    val name: String,
    val phoneNumber: String
)

object ContactMatcher {

    private val cyrillicToLatinMap = mapOf(
        'а' to "a", 'б' to "b", 'в' to "v", 'г' to "g", 'ғ' to "g",
        'д' to "d", 'е' to "e", 'ё' to "yo", 'ж' to "j", 'з' to "z",
        'и' to "i", 'й' to "y", 'к' to "k", 'қ' to "q", 'л' to "l",
        'м' to "m", 'н' to "n", 'о' to "o", 'ў' to "o", 'п' to "p",
        'р' to "r", 'с' to "s", 'т' to "t", 'у' to "u", 'ф' to "f",
        'х' to "x", 'ҳ' to "h", 'ц' to "ts", 'ч' to "ch", 'ш' to "sh",
        'щ' to "sh", 'ъ' to "", 'ы' to "i", 'ь' to "", 'э' to "e",
        'ю' to "yu", 'я' to "ya"
    )

    fun normalizeName(raw: String): String {
        val lower = raw.lowercase().trim()
        val sb = StringBuilder()
        for (ch in lower) {
            if (cyrillicToLatinMap.containsKey(ch)) {
                sb.append(cyrillicToLatinMap[ch])
            } else if (ch in 'a'..'z' || ch in '0'..'9') {
                sb.append(ch)
            }
        }
        return sb.toString()
            .replace("o'", "o")
            .replace("g'", "g")
            .replace("kh", "x")
            .replace("h", "x")
    }

    fun findContacts(context: Context, spokenQuery: String): List<MatchedContact> {
        val targetNorm = normalizeName(spokenQuery)
        if (targetNorm.length < 2) return emptyList()

        val results = mutableListOf<MatchedContact>()
        val seenNumbers = mutableSetOf<String>()

        val cursor = context.contentResolver.query(
            ContactsContract.CommonDataKinds.Phone.CONTENT_URI,
            arrayOf(
                ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME,
                ContactsContract.CommonDataKinds.Phone.NUMBER
            ),
            null,
            null,
            null
        )

        cursor?.use {
            val nameIdx = it.getColumnIndex(ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME)
            val numIdx = it.getColumnIndex(ContactsContract.CommonDataKinds.Phone.NUMBER)
            while (it.moveToNext()) {
                val displayName = it.getString(nameIdx) ?: continue
                val number = (it.getString(numIdx) ?: continue).replace("\\s+".toRegex(), "")
                if (seenNumbers.contains(number)) continue

                val contactNorm = normalizeName(displayName)
                if (contactNorm == targetNorm ||
                    contactNorm.contains(targetNorm) ||
                    targetNorm.contains(contactNorm) ||
                    levenshteinDistance(contactNorm, targetNorm) <= 2
                ) {
                    seenNumbers.add(number)
                    results.add(MatchedContact(displayName, number))
                }
            }
        }
        return results
    }

    private fun levenshteinDistance(a: String, b: String): Int {
        if (a.isEmpty()) return b.length
        if (b.isEmpty()) return a.length
        val dp = IntArray(b.length + 1) { it }
        for (i in 1..a.length) {
            var prev = dp[0]
            dp[0] = i
            for (j in 1..b.length) {
                val temp = dp[j]
                val cost = if (a[i - 1] == b[j - 1]) 0 else 1
                dp[j] = minOf(dp[j] + 1, dp[j - 1] + 1, prev + cost)
                prev = temp
            }
        }
        return dp[b.length]
    }
}
""",
    "app/src/main/java/com/example/toibot/ToibotAccessibilityService.kt": """package com.example.toibot

import android.accessibilityservice.AccessibilityService
import android.os.Build
import android.os.Handler
import android.os.Looper
import android.view.Display
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo

class ToibotAccessibilityService : AccessibilityService() {

    companion object {
        var instance: ToibotAccessibilityService? = null
    }

    private val handler = Handler(Looper.getMainLooper())

    override fun onServiceConnected() {
        super.onServiceConnected()
        instance = this
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {}

    override fun onInterrupt() {}

    override fun onDestroy() {
        super.onDestroy()
        instance = null
    }

    fun takeSystemScreenshot(onResult: (Boolean) -> Unit) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
            takeScreenshot(
                Display.DEFAULT_DISPLAY,
                mainExecutor,
                object : TakeScreenshotCallback {
                    override fun onSuccess(screenshot: ScreenshotResult) {
                        screenshot.hardwareBuffer.close()
                        onResult(true)
                    }
                    override fun onFailure(errorCode: Int) {
                        onResult(false)
                    }
                }
            )
        } else if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            val ok = performGlobalAction(GLOBAL_ACTION_TAKE_SCREENSHOT)
            onResult(ok)
        } else {
            onResult(false)
        }
    }

    fun scrollDownActiveScreen(): Boolean {
        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
            performGlobalAction(GLOBAL_ACTION_SCROLL_FORWARD)
        } else {
            false
        }
    }

    fun goBack(): Boolean = performGlobalAction(GLOBAL_ACTION_BACK)

    fun goHome(): Boolean = performGlobalAction(GLOBAL_ACTION_HOME)

    fun clickFirstVideoResultAfterDelay(delayMs: Long = 2200L, onDone: ((Boolean) -> Unit)? = null) {
        handler.postDelayed({
            val clicked = clickFirstClickableVideoCandidate()
            onDone?.invoke(clicked)
        }, delayMs)
    }

    private fun clickFirstClickableVideoCandidate(): Boolean {
        val root = rootInActiveWindow ?: return false
        val queue = ArrayDeque<AccessibilityNodeInfo>()
        queue.add(root)

        val candidates = mutableListOf<AccessibilityNodeInfo>()
        while (queue.isNotEmpty()) {
            val node = queue.removeFirst()
            val desc = node.contentDescription?.toString()?.trim() ?: ""
            val txt = node.text?.toString()?.trim() ?: ""
            val hasMeaningfulLabel = desc.length > 6 || txt.length > 6

            if (node.isClickable && hasMeaningfulLabel) {
                val lowerLabel = "$desc $txt".lowercase()
                val isNavOrFilter = lowerLabel.contains("home") ||
                    lowerLabel.contains("shorts") ||
                    lowerLabel.contains("subscriptions") ||
                    lowerLabel.contains("library") ||
                    lowerLabel.contains("all") ||
                    lowerLabel.contains("filter") ||
                    lowerLabel.contains("search")
                if (!isNavOrFilter) {
                    candidates.add(node)
                }
            }

            for (i in 0 until node.childCount) {
                node.getChild(i)?.let { queue.add(it) }
            }
        }

        for (candidate in candidates) {
            if (candidate.performAction(AccessibilityNodeInfo.ACTION_CLICK)) {
                return true
            }
            var parent = candidate.parent
            var depth = 0
            while (parent != null && depth < 3) {
                if (parent.isClickable && parent.performAction(AccessibilityNodeInfo.ACTION_CLICK)) {
                    return true
                }
                parent = parent.parent
                depth++
            }
        }
        return false
    }
}
""",
    "app/src/main/java/com/example/toibot/ToibotCommandEngine.kt": """package com.example.toibot

import android.content.Context
import android.content.Intent
import android.hardware.camera2.CameraManager
import android.media.AudioManager
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.net.Uri
import android.os.BatteryManager
import android.os.Build
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import android.provider.AlarmClock
import android.provider.Settings
import android.telephony.SmsManager
import android.view.KeyEvent
import org.json.JSONArray
import org.json.JSONObject
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

data class PendingConfirmation(
    val descriptionForSpeech: String,
    val executeAction: () -> String
)

class ToibotCommandEngine(private val context: Context) {

    var pendingAction: PendingConfirmation? = null
    private val memoryPrefs = context.getSharedPreferences("toibot_memory", Context.MODE_PRIVATE)
    private val offlineJokes = listOf(
        "Dasturchi do'stidan so'rabdi: Nimaga kod yozishdan oldin choy damlaysan? Chunki kod birinchi urinishdayoq ishlasa, yuragim ko'tarmaydi!",
        "Kompyuter nega sovqotadi? Chunki hamma Windows oynalarini ochib qo'ygan!",
        "Robotdan so'rashibdi: Charchamadingmi? Robot debdi: Batareyam 90 foiz, hali sizni ham uxlating deb turibman!"
    )

    fun isOnline(): Boolean {
        val cm = context.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        val net = cm.activeNetwork ?: return false
        val caps = cm.getNetworkCapabilities(net) ?: return false
        return caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
    }

    fun saveApiKey(key: String) {
        memoryPrefs.edit().putString("gemini_api_key", key.trim()).apply()
    }

    fun getApiKey(): String = memoryPrefs.getString("gemini_api_key", "") ?: ""

    fun saveCustomMixUrl(url: String) {
        memoryPrefs.edit().putString("custom_mix_url", url.trim()).apply()
    }

    fun getCustomMixUrl(): String = memoryPrefs.getString("custom_mix_url", "") ?: ""

    fun processCommand(
        rawSpeech: String,
        onSpeak: (String) -> Unit,
        onConfirmationRequested: (String) -> Unit
    ) {
        val speech = rawSpeech.trim()
        val lower = speech.lowercase()

        val currentPending = pendingAction
        if (currentPending != null) {
            when {
                lower.contains("ha") || lower.contains("tasdiqlayman") ||
                lower.contains("yubor") || lower.contains("mayli") ||
                lower.contains("да") || lower.contains("yes") -> {
                    pendingAction = null
                    val resultMsg = currentPending.executeAction()
                    onSpeak(resultMsg)
                    return
                }
                lower.contains("yo'q") || lower.contains("bekor") ||
                lower.contains("to'xta") || lower.contains("нет") || lower.contains("no") -> {
                    pendingAction = null
                    onSpeak("Bekor qilindi, T.O.I.B.O.T kutish rejimida.")
                    return
                }
            }
        }

        if (lower.contains("salom") || lower.contains("assalomu alaykum") || lower == "alo") {
            onSpeak("Va alaykum assalom! T.O.I.B.O.T xizmatingizda. Nima buyurasiz?")
            return
        }
        if (lower.contains("nima gap") || lower.contains("qalaysan") || lower.contains("o'zingizdachi") || lower.contains("uzingizdachi")) {
            onSpeak("Hammasi joyida, tizim barqaror ishlayapti. O'zingizda nima gaplar?")
            return
        }
        if (lower.contains("bugun nimalar qilmoqchisiz") || lower.contains("nima qila olasan")) {
            onSpeak("Bugun sizga qo'ng'iroq qilish, SMS yozish, YouTube'da musiqa qo'yish, skrinshot olish va savollaringizga javob berishga tayyorman.")
            return
        }
        if (lower.contains("hazil") || lower.contains("latifa")) {
            onSpeak(offlineJokes.random())
            return
        }

        if (lower.contains("mening miksim") || lower.contains("miksimni qo'y") ||
            lower.contains("miksimni yoq") || lower.contains("my mix")
        ) {
            val savedMixUrl = getCustomMixUrl()
            if (savedMixUrl.isNotBlank()) {
                openUrl(savedMixUrl)
                ToibotAccessibilityService.instance?.clickFirstVideoResultAfterDelay(2400L)
                onSpeak("Sizning shaxsiy miksingiz YouTube'da ishga tushirilmoqda.")
            } else {
                val mixQuery = URLEncoder.encode("My Mix music playlist", "UTF-8")
                openUrl("https://www.youtube.com/results?search_query=$mixQuery")
                ToibotAccessibilityService.instance?.clickFirstVideoResultAfterDelay(2400L)
                onSpeak("YouTube'da sizning miksingiz qidirilmoqda va birinchi natija ochilmoqda.")
            }
            return
        }

        val isPlayRequest = lower.contains("qo'y") || lower.contains("quys") ||
            lower.contains("yoq") || lower.contains("ijro et") || lower.contains("play")
        if (lower.contains("youtube") && (isPlayRequest || lower.contains("qidir") || lower.contains("och"))) {
            val cleanedQuery = speech
                .replace("youtube", "", ignoreCase = true)
                .replace("da", "", ignoreCase = true)
                .replace("qo'shig'ini", "", ignoreCase = true)
                .replace("qo'shiq", "", ignoreCase = true)
                .replace("qushiq", "", ignoreCase = true)
                .replace("birinchi videoni", "", ignoreCase = true)
                .replace("videoni", "", ignoreCase = true)
                .replace("qo'y", "", ignoreCase = true)
                .replace("quys", "", ignoreCase = true)
                .replace("yoq", "", ignoreCase = true)
                .replace("qidir", "", ignoreCase = true)
                .replace("och", "", ignoreCase = true)
                .trim()

            if (cleanedQuery.isNotEmpty()) {
                val encoded = URLEncoder.encode(cleanedQuery, "UTF-8")
                openUrl("https://www.youtube.com/results?search_query=$encoded")
                if (isPlayRequest || lower.contains("birinchi")) {
                    ToibotAccessibilityService.instance?.clickFirstVideoResultAfterDelay(2400L)
                    onSpeak("YouTube'da $cleanedQuery topildi va birinchi video ishga tushirilmoqda.")
                } else {
                    onSpeak("YouTube'da $cleanedQuery qidirildi.")
                }
            } else {
                openUrl("https://www.youtube.com")
                onSpeak("YouTube ochildi.")
            }
            return
        }

        if (lower.contains("skrinshot") || lower.contains("ekranni rasmga") || lower.contains("screenshot")) {
            val acc = ToibotAccessibilityService.instance
            if (acc != null) {
                acc.takeSystemScreenshot { ok ->
                    onSpeak(if (ok) "Skrinshot olindi." else "Skrinshot olib bo'lmadi.")
                }
            } else {
                context.startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
                onSpeak("Skrinshot olish uchun Maxsus imkoniyatlar bo'limidan T.O.I.B.O.T xizmatini yoqing.")
            }
            return
        }

        if (lower.contains("orqaga qayt") || lower.contains("nazad")) {
            val ok = ToibotAccessibilityService.instance?.goBack() ?: false
            onSpeak(if (ok) "Orqaga qaytdim." else "Maxsus xizmat faol emas.")
            return
        }
        if (lower.contains("bosh ekran") || lower.contains("domoy")) {
            val ok = ToibotAccessibilityService.instance?.goHome() ?: false
            onSpeak(if (ok) "Bosh ekranga qaytdim." else "Maxsus xizmat faol emas.")
            return
        }
        if (lower.contains("pastga tushir") || lower.contains("skroll")) {
            val ok = ToibotAccessibilityService.instance?.scrollDownActiveScreen() ?: false
            onSpeak(if (ok) "Sahifa pastga aylantirildi." else "Sahifani aylantirib bo'lmadi.")
            return
        }

        if (lower.contains("e.maktab") || lower.contains("emaktab") || lower.contains("e maktab")) {
            openUrl("https://login.emaktab.uz")
            onSpeak("e.maktab sahifasi ochildi.")
            return
        }
        if (lower.contains("googledan") || lower.contains("google dan") || lower.contains("qidir")) {
            val query = speech
                .replace("googledan", "", ignoreCase = true)
                .replace("google dan", "", ignoreCase = true)
                .replace("qidir", "", ignoreCase = true)
                .trim()
            if (query.isNotEmpty()) {
                val encoded = URLEncoder.encode(query, "UTF-8")
                openUrl("https://www.google.com/search?q=$encoded")
                onSpeak("Google orqali $query bo'yicha qidiruv ochildi.")
            } else {
                openUrl("https://www.google.com")
                onSpeak("Google ochildi.")
            }
            return
        }

        if ((lower.contains("telegram") || lower.contains("whatsapp") || lower.contains("vatsap")) &&
            (lower.contains("yoz") || lower.contains("xabar") || lower.contains("habar"))
        ) {
            handleMessengerCommand(speech, onSpeak, onConfirmationRequested)
            return
        }

        if (lower.contains("sms") || lower.contains("xabar yoz") || lower.contains("habar yoz")) {
            handleSmsCommand(speech, onSpeak, onConfirmationRequested)
            return
        }

        if (lower.contains("qo'ng'iroq") || lower.contains("qongiroq") ||
            lower.contains("telefon qil") || lower.contains("zvonok") || lower.contains("позвони")
        ) {
            handleCallCommand(speech, onSpeak, onConfirmationRequested)
            return
        }

        if (lower.contains("fonar") || lower.contains("chiroq")) {
            val turnOn = lower.contains("yoq") || lower.contains("yondir")
            toggleFlashlight(turnOn)
            onSpeak(if (turnOn) "Chiroq yoqildi." else "Chiroq o'chirildi.")
            return
        }

        if (lower.contains("vibratsiya") || lower.contains("titra")) {
            vibrateBriefly()
            onSpeak("Vibratsiya signali bajarildi.")
            return
        }

        if (lower.contains("musiqani to'xtat") || lower.contains("pauza") || lower.contains("davom ettir")) {
            sendMediaKey(KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE)
            onSpeak("Media holati o'zgartirildi.")
            return
        }

        if (lower.contains("ovozni balandlat") || lower.contains("ovozni ko'tar")) {
            val am = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
            am.adjustVolume(AudioManager.ADJUST_RAISE, AudioManager.FLAG_SHOW_UI)
            onSpeak("Ovoz balandlatildi.")
            return
        }
        if (lower.contains("ovozni pasaytir") || lower.contains("ovozni tushir")) {
            val am = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
            am.adjustVolume(AudioManager.ADJUST_LOWER, AudioManager.FLAG_SHOW_UI)
            onSpeak("Ovoz pasaytirildi.")
            return
        }

        if (lower.contains("soat") || lower.contains("vaqt")) {
            val time = SimpleDateFormat("HH:mm", Locale.getDefault()).format(Date())
            onSpeak("Hozir soat $time.")
            return
        }
        if (lower.contains("sana") || lower.contains("bugun nechanchi")) {
            val dateStr = SimpleDateFormat("dd.MM.yyyy", Locale.getDefault()).format(Date())
            onSpeak("Bugungi sana $dateStr.")
            return
        }
        if (lower.contains("batareya") || lower.contains("quvvat")) {
            val bm = context.getSystemService(Context.BATTERY_SERVICE) as BatteryManager
            val pct = bm.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY)
            onSpeak("Batareya quvvati $pct foiz.")
            return
        }

        if (lower.contains("taymer")) {
            val mins = Regex("\\d+").find(lower)?.value?.toIntOrNull() ?: 1
            val intent = Intent(AlarmClock.ACTION_SET_TIMER).apply {
                putExtra(AlarmClock.EXTRA_LENGTH, mins * 60)
                putExtra(AlarmClock.EXTRA_SKIP_UI, true)
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            }
            context.startActivity(intent)
            onSpeak("$mins daqiqalik taymer o'rnatildi.")
            return
        }

        if (lower.contains("qo'sh") || lower.contains("ayir") || lower.contains("ko'paytir") ||
            lower.contains("karra") || lower.contains("bo'l") || lower.contains("hisobla") ||
            lower.contains("+") || lower.contains("-") || lower.contains("*") || lower.contains("/")
        ) {
            val nums = Regex("\\d+(\\.\\d+)?").findAll(lower).mapNotNull { it.value.toDoubleOrNull() }.toList()
            if (nums.size >= 2) {
                val res = when {
                    lower.contains("qo'sh") || lower.contains("plus") || lower.contains("+") -> nums[0] + nums[1]
                    lower.contains("ayir") || lower.contains("minus") || lower.contains("-") -> nums[0] - nums[1]
                    lower.contains("ko'paytir") || lower.contains("karra") || lower.contains("*") || lower.contains("x") -> nums[0] * nums[1]
                    lower.contains("bo'l") || lower.contains("/") -> if (nums[1] != 0.0) nums[0] / nums[1] else Double.NaN
                    else -> nums.sum()
                }
                if (!res.isNaN()) {
                    val formatted = if (res % 1.0 == 0.0) res.toLong().toString() else String.format(Locale.US, "%.2f", res)
                    onSpeak("Hisob natijasi: $formatted")
                    return
                }
            }
        }

        if (lower.contains("eslab qol")) {
            val fact = speech.replace("eslab qol", "", ignoreCase = true).trim()
            val oldNotes = memoryPrefs.getString("saved_notes", "") ?: ""
            memoryPrefs.edit().putString("saved_notes", "$oldNotes\n- $fact").apply()
            onSpeak("Xotiraga saqlandi: $fact")
            return
        }
        if (lower.contains("nimani eslab qolgansan") || lower.contains("eslatmalar")) {
            val notes = memoryPrefs.getString("saved_notes", "") ?: ""
            onSpeak(if (notes.isBlank()) "Hozircha saqlangan eslatmalar yo'q." else "Saqlangan ma'lumotlar: $notes")
            return
        }

        if (isOnline() && getApiKey().isNotBlank()) {
            val aiReply = askGeminiOnline(speech)
            onSpeak(aiReply)
        } else {
            onSpeak("Oflayn rejimda buyruq qabul qilindi: $speech.")
        }
    }

    private fun handleCallCommand(
        speech: String,
        onSpeak: (String) -> Unit,
        onConfirmationRequested: (String) -> Unit
    ) {
        val cleaned = speech
            .replace("qo'ng'iroq qil", "", ignoreCase = true)
            .replace("qongiroq qil", "", ignoreCase = true)
            .replace("telefon qil", "", ignoreCase = true)
            .replace("ga", "", ignoreCase = true)
            .trim()

        val matches = ContactMatcher.findContacts(context, cleaned)
        if (matches.isEmpty()) {
            onSpeak("$cleaned ismli kontakt topilmadi.")
            return
        }
        val target = matches.first()
        val prompt = "${target.name} raqamiga qo'ng'iroq qilaymi? Tasdiqlang."
        pendingAction = PendingConfirmation(prompt) {
            val intent = Intent(Intent.ACTION_CALL, Uri.parse("tel:${target.phoneNumber}")).apply {
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            }
            context.startActivity(intent)
            "${target.name} ga qo'ng'iroq qilinmoqda."
        }
        onConfirmationRequested(prompt)
    }

    private fun handleSmsCommand(
        speech: String,
        onSpeak: (String) -> Unit,
        onConfirmationRequested: (String) -> Unit
    ) {
        val parts = speech.split(":", "deb", limit = 2)
        val header = parts[0]
        val messageBody = if (parts.size > 1) parts[1].trim() else "Salom!"

        val namePart = header
            .replace("sms yoz", "", ignoreCase = true)
            .replace("sms yubor", "", ignoreCase = true)
            .replace("xabar yoz", "", ignoreCase = true)
            .replace("habar yoz", "", ignoreCase = true)
            .replace("ga", "", ignoreCase = true)
            .trim()

        val matches = ContactMatcher.findContacts(context, namePart)
        if (matches.isEmpty()) {
            onSpeak("$namePart ismli kontakt topilmadi.")
            return
        }
        val target = matches.first()
        val prompt = "${target.name} ga quyidagi SMS yuborilsinmi: $messageBody. Tasdiqlaysizmi?"
        pendingAction = PendingConfirmation(prompt) {
            val smsManager = context.getSystemService(SmsManager::class.java)
            smsManager.sendTextMessage(target.phoneNumber, null, messageBody, null, null)
            "${target.name} ga SMS yuborildi."
        }
        onConfirmationRequested(prompt)
    }

    private fun handleMessengerCommand(
        speech: String,
        onSpeak: (String) -> Unit,
        onConfirmationRequested: (String) -> Unit
    ) {
        val isTelegram = speech.contains("telegram", ignoreCase = true)
        val appName = if (isTelegram) "Telegram" else "WhatsApp"
        val pkg = if (isTelegram) "org.telegram.messenger" else "com.whatsapp"

        val parts = speech.split(":", "deb", limit = 2)
        val messageText = if (parts.size > 1) parts[1].trim() else speech

        val prompt = "$appName orqali quyidagi matn yuborilsinmi: $messageText. Tasdiqlaysizmi?"
        pendingAction = PendingConfirmation(prompt) {
            val sendIntent = Intent(Intent.ACTION_SEND).apply {
                type = "text/plain"
                putExtra(Intent.EXTRA_TEXT, messageText)
                setPackage(pkg)
                addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
            }
            try {
                context.startActivity(sendIntent)
                "$appName oynasi ochildi va matn tayyorlandi."
            } catch (e: Exception) {
                "$appName ilovasi qurilmada topilmadi."
            }
        }
        onConfirmationRequested(prompt)
    }

    private fun openUrl(url: String) {
        val intent = Intent(Intent.ACTION_VIEW, Uri.parse(url)).apply {
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        context.startActivity(intent)
    }

    private fun toggleFlashlight(enable: Boolean) {
        try {
            val cm = context.getSystemService(Context.CAMERA_SERVICE) as CameraManager
            val cameraId = cm.cameraIdList.firstOrNull() ?: return
            cm.setTorchMode(cameraId, enable)
        } catch (_: Exception) {
        }
    }

    private fun vibrateBriefly() {
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                val vm = context.getSystemService(Context.VIBRATOR_MANAGER_SERVICE) as VibratorManager
                vm.defaultVibrator.vibrate(VibrationEffect.createOneShot(180, VibrationEffect.DEFAULT_AMPLITUDE))
            } else {
                @Suppress("DEPRECATION")
                val v = context.getSystemService(Context.VIBRATOR_SERVICE) as Vibrator
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    v.vibrate(VibrationEffect.createOneShot(180, VibrationEffect.DEFAULT_AMPLITUDE))
                } else {
                    @Suppress("DEPRECATION")
                    v.vibrate(180)
                }
            }
        } catch (_: Exception) {
        }
    }

    private fun sendMediaKey(keyCode: Int) {
        val am = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
        am.dispatchMediaKeyEvent(KeyEvent(KeyEvent.ACTION_DOWN, keyCode))
        am.dispatchMediaKeyEvent(KeyEvent(KeyEvent.ACTION_UP, keyCode))
    }

    private fun askGeminiOnline(prompt: String): String {
        return try {
            val apiKey = getApiKey()
            val url = URL("https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key=$apiKey")
            val conn = (url.openConnection() as HttpURLConnection).apply {
                requestMethod = "POST"
                setRequestProperty("Content-Type", "application/json")
                doOutput = true
                connectTimeout = 8000
                readTimeout = 12000
            }

            val systemStyle = "Sen T.O.I.B.O.T mustaqil gibrid yordamchisiz. Vazmin, qisqa, aqlli va o'zbek tilida javob ber."
            val payload = JSONObject().apply {
                put("contents", JSONArray().put(JSONObject().apply {
                    put("parts", JSONArray().put(JSONObject().apply {
                        put("text", "$systemStyle\nFoydalanuvchi: $prompt")
                    }))
                }))
            }

            OutputStreamWriter(conn.outputStream).use { it.write(payload.toString()) }
            val responseText = conn.inputStream.bufferedReader().readText()
            val json = JSONObject(responseText)
            json.getJSONArray("candidates")
                .getJSONObject(0)
                .getJSONObject("content")
                .getJSONArray("parts")
                .getJSONObject(0)
                .getString("text")
        } catch (e: Exception) {
            "Onlayn AI bilan bog'lanishda xatolik: ${e.message}"
        }
    }
}
""",
    "app/src/main/java/com/example/toibot/ToibotForegroundService.kt": """package com.example.toibot

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.Service
import android.content.Intent
import android.graphics.Color
import android.graphics.PixelFormat
import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioTrack
import android.os.Build
import android.os.IBinder
import android.provider.Settings
import android.view.Gravity
import android.view.WindowManager
import android.widget.LinearLayout
import android.widget.TextView
import androidx.core.app.NotificationCompat
import com.k2fsa.sherpa.onnx.OfflineTts
import com.k2fsa.sherpa.onnx.OfflineTtsConfig
import com.k2fsa.sherpa.onnx.OfflineTtsModelConfig
import com.k2fsa.sherpa.onnx.OfflineTtsVitsModelConfig
import org.json.JSONObject
import org.vosk.Model
import org.vosk.Recognizer
import org.vosk.android.RecognitionListener
import org.vosk.android.SpeechService
import org.vosk.android.StorageService
import kotlin.concurrent.thread
import kotlin.math.abs

class ToibotForegroundService : Service(), RecognitionListener {

    private var sttModel: Model? = null
    private var speechService: SpeechService? = null
    private var offlineTts: OfflineTts? = null
    private lateinit var commandEngine: ToibotCommandEngine

    private var windowManager: WindowManager? = null
    private var overlayContainer: LinearLayout? = null
    private var orbView: ToibotOrbView? = null
    private var subtitleText: TextView? = null

    @Volatile
    private var isSpeakingNow = false

    override fun onCreate() {
        super.onCreate()
        commandEngine = ToibotCommandEngine(this)
        startForegroundNotification()
        setupFloatingMiniOrb()
        initModels()
    }

    private fun startForegroundNotification() {
        val channelId = "toibot_always_on"
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                channelId,
                "T.O.I.B.O.T Always-On Listener",
                NotificationManager.IMPORTANCE_LOW
            )
            val nm = getSystemService(NotificationManager::class.java)
            nm.createNotificationChannel(channel)
        }

        val notification: Notification = NotificationCompat.Builder(this, channelId)
            .setContentTitle("T.O.I.B.O.T faol")
            .setContentText("Doimiy jim eshitish rejimi ishlamoqda")
            .setSmallIcon(android.R.drawable.ic_btn_speak_now)
            .build()

        startForeground(101, notification)
    }

    private fun setupFloatingMiniOrb() {
        if (!Settings.canDrawOverlays(this)) return

        windowManager = getSystemService(WINDOW_SERVICE) as WindowManager
        overlayContainer = LinearLayout(this).apply {
            orientation = LinearLayout.HORIZONTAL
            gravity = Gravity.CENTER_VERTICAL
            setBackgroundColor(Color.parseColor("#CC050B0E"))
            setPadding(24, 14, 28, 14)
        }

        orbView = ToibotOrbView(this).apply {
            layoutParams = LinearLayout.LayoutParams(120, 120)
        }

        subtitleText = TextView(this).apply {
            text = "T.O.I.B.O.T tayyor"
            setTextColor(Color.parseColor("#E0F2FE"))
            textSize = 14f
            maxLines = 2
            setPadding(20, 0, 0, 0)
        }

        overlayContainer?.addView(orbView)
        overlayContainer?.addView(subtitleText)

        val overlayType = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY
        } else {
            @Suppress("DEPRECATION")
            WindowManager.LayoutParams.TYPE_PHONE
        }

        val params = WindowManager.LayoutParams(
            WindowManager.LayoutParams.WRAP_CONTENT,
            WindowManager.LayoutParams.WRAP_CONTENT,
            overlayType,
            WindowManager.LayoutParams.FLAG_NOT_FOCUSABLE or WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN,
            PixelFormat.TRANSLUCENT
        ).apply {
            gravity = Gravity.TOP or Gravity.CENTER_HORIZONTAL
            y = 48
        }

        windowManager?.addView(overlayContainer, params)
    }

    private fun initModels() {
        thread {
            StorageService.unpack(this, "tts_model", "tts_model",
                { unpackedTts ->
                    try {
                        val ttsDir = unpackedTts.absolutePath
                        val vitsConfig = OfflineTtsVitsModelConfig(
                            model = "$ttsDir/model.onnx",
                            tokens = "$ttsDir/tokens.txt",
                            dataDir = "$ttsDir/espeak-ng-data"
                        )
                        val modelConfig = OfflineTtsModelConfig(
                            vits = vitsConfig,
                            numThreads = 2,
                            debug = false
                        )
                        offlineTts = OfflineTts(config = OfflineTtsConfig(model = modelConfig))
                    } catch (_: Exception) {
                    }
                },
                { }
            )

            StorageService.unpack(this, "stt_model", "stt_model",
                { unpackedStt ->
                    sttModel = unpackedStt
                    startContinuousListening()
                },
                { e ->
                    updateOverlay(ToibotOrbView.OrbState.IDLE, "STT model topilmadi: ${e.message}", 0f)
                }
            )
        }
    }

    private fun startContinuousListening() {
        val model = sttModel ?: return
        speechService?.stop()
        val recognizer = Recognizer(model, 16000.0f)
        speechService = SpeechService(recognizer, 16000.0f)
        speechService?.startListening(this)
        updateOverlay(ToibotOrbView.OrbState.LISTENING, "Eshitmoqdaman...", 0.1f)
    }

    override fun onPartialResult(hypothesis: String?) {
        if (isSpeakingNow) return
        val partial = JSONObject(hypothesis ?: "{}").optString("partial", "")
        if (partial.isNotBlank()) {
            updateOverlay(ToibotOrbView.OrbState.LISTENING, partial, 0.55f)
        }
    }

    override fun onResult(hypothesis: String?) {
        if (isSpeakingNow) return
        val text = JSONObject(hypothesis ?: "{}").optString("text", "")
        if (text.isNotBlank()) {
            updateOverlay(ToibotOrbView.OrbState.LISTENING, text, 0.7f)
            thread {
                commandEngine.processCommand(
                    rawSpeech = text,
                    onSpeak = { reply -> speakIndependently(reply, confirming = false) },
                    onConfirmationRequested = { prompt -> speakIndependently(prompt, confirming = true) }
                )
            }
        }
    }

    override fun onFinalResult(hypothesis: String?) {}
    override fun onError(exception: Exception?) {}
    override fun onTimeout() {}

    private fun speakIndependently(text: String, confirming: Boolean) {
        isSpeakingNow = true
        speechService?.setPause(true)
        val targetState = if (confirming) ToibotOrbView.OrbState.CONFIRMING else ToibotOrbView.OrbState.SPEAKING
        updateOverlay(targetState, text, 0.8f)

        val ttsEngine = offlineTts
        if (ttsEngine != null) {
            val audio = ttsEngine.generate(text = text, sid = 0, speed = 0.92f)
            playPcmWithOrbSync(audio.samples, audio.sampleRate, targetState, text)
        } else {
            Thread.sleep(1500)
        }

        isSpeakingNow = false
        speechService?.setPause(false)
        updateOverlay(
            if (confirming) ToibotOrbView.OrbState.CONFIRMING else ToibotOrbView.OrbState.LISTENING,
            if (confirming) "Tasdiqlash kutilmoqda: Ha / Yo'q" else "Eshitmoqdaman...",
            0.1f
        )
    }

    private fun playPcmWithOrbSync(
        samples: FloatArray,
        sampleRate: Int,
        state: ToibotOrbView.OrbState,
        caption: String
    ) {
        if (samples.isEmpty()) return
        val pcm16 = ShortArray(samples.size) { i ->
            (samples[i].coerceIn(-1.0f, 1.0f) * Short.MAX_VALUE).toInt().toShort()
        }
        val minBufSize = AudioTrack.getMinBufferSize(
            sampleRate,
            AudioFormat.CHANNEL_OUT_MONO,
            AudioFormat.ENCODING_PCM_16BIT
        )
        val audioTrack = AudioTrack.Builder()
            .setAudioAttributes(
                AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_ASSISTANT)
                    .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                    .build()
            )
            .setAudioFormat(
                AudioFormat.Builder()
                    .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                    .setSampleRate(sampleRate)
                    .setChannelMask(AudioFormat.CHANNEL_OUT_MONO)
                    .build()
            )
            .setBufferSizeInBytes(maxOf(minBufSize, pcm16.size * 2))
            .setTransferMode(AudioTrack.MODE_STATIC)
            .build()

        audioTrack.write(pcm16, 0, pcm16.size)
        audioTrack.play()

        val durationMs = (samples.size * 1000L) / sampleRate
        val stepMs = 60L
        var elapsed = 0L
        while (elapsed < durationMs) {
            val idx = ((elapsed * samples.size) / durationMs).toInt().coerceIn(0, samples.size - 1)
            val amp = abs(samples[idx]) * 2.5f
            updateOverlay(state, caption, amp)
            Thread.sleep(stepMs)
            elapsed += stepMs
        }
        audioTrack.stop()
        audioTrack.release()
    }

    private fun updateOverlay(state: ToibotOrbView.OrbState, caption: String, amp: Float) {
        overlayContainer?.post {
            orbView?.state = state
            orbView?.audioAmplitude = amp
            subtitleText?.text = caption
        }
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onDestroy() {
        super.onDestroy()
        speechService?.stop()
        offlineTts?.release()
        if (overlayContainer != null) {
            windowManager?.removeView(overlayContainer)
        }
    }
}
""",
    "app/src/main/java/com/example/toibot/MainActivity.kt": """package com.example.toibot

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Color
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.view.Gravity
import android.widget.Button
import android.widget.EditText
import android.widget.LinearLayout
import android.widget.ScrollView
import android.widget.TextView
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat

class MainActivity : AppCompatActivity() {

    private lateinit var commandEngine: ToibotCommandEngine
    private lateinit var miniOrbPreview: ToibotOrbView
    private lateinit var statusLabel: TextView

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        commandEngine = ToibotCommandEngine(this)

        val rootScroll = ScrollView(this).apply {
            setBackgroundColor(Color.parseColor("#04090C"))
        }

        val container = LinearLayout(this).apply {
            orientation = LinearLayout.VERTICAL
            gravity = Gravity.CENTER_HORIZONTAL
            setPadding(40, 48, 40, 48)
        }

        miniOrbPreview = ToibotOrbView(this).apply {
            layoutParams = LinearLayout.LayoutParams(180, 180)
            state = ToibotOrbView.OrbState.LISTENING
        }

        statusLabel = TextView(this).apply {
            text = "T.O.I.B.O.T Gibrid Tizim (Onlayn + Oflayn)"
            setTextColor(Color.parseColor("#2DD4BF"))
            textSize = 18f
            gravity = Gravity.CENTER
            setPadding(0, 16, 0, 24)
        }

        val apiInput = EditText(this).apply {
            hint = "Gemini API kaliti (onlayn AI uchun ixtiyoriy)"
            setText(commandEngine.getApiKey())
            setTextColor(Color.WHITE)
            setHintTextColor(Color.GRAY)
        }

        val saveApiBtn = Button(this).apply {
            text = "API kalitni saqlash"
            setOnClickListener {
                commandEngine.saveApiKey(apiInput.text.toString())
                statusLabel.text = "API kalit saqlandi."
            }
        }

        val mixUrlInput = EditText(this).apply {
            hint = "YouTube miks havolasi (ixtiyoriy, masalan: youtube.com/watch?v=...)"
            setText(commandEngine.getCustomMixUrl())
            setTextColor(Color.WHITE)
            setHintTextColor(Color.GRAY)
        }

        val saveMixBtn = Button(this).apply {
            text = "Mening miksim havolasini saqlash"
            setOnClickListener {
                commandEngine.saveCustomMixUrl(mixUrlInput.text.toString())
                statusLabel.text = "YouTube miks havolasi saqlandi."
            }
        }

        val overlayPermBtn = Button(this).apply {
            text = "1. Ekran ustida kichik sfera ruxsati"
            setOnClickListener {
                if (!Settings.canDrawOverlays(this@MainActivity)) {
                    val intent = Intent(
                        Settings.ACTION_MANAGE_OVERLAY_PERMISSION,
                        Uri.parse("package:$packageName")
                    )
                    startActivity(intent)
                } else {
                    statusLabel.text = "Ekran usti ruxsati allaqachon berilgan."
                }
            }
        }

        val accPermBtn = Button(this).apply {
            text = "2. Skrinshot va avto-boshqaruv ruxsati"
            setOnClickListener {
                startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
            }
        }

        val startToibotBtn = Button(this).apply {
            text = "T.O.I.B.O.T Doimiy Eshitishni Ishga Tushirish"
            setOnClickListener {
                requestAllPermissionsAndStart()
            }
        }

        val stopToibotBtn = Button(this).apply {
            text = "To'xtatish"
            setOnClickListener {
                stopService(Intent(this@MainActivity, ToibotForegroundService::class.java))
                statusLabel.text = "T.O.I.B.O.T to'xtatildi."
            }
        }

        container.addView(miniOrbPreview)
        container.addView(statusLabel)
        container.addView(apiInput)
        container.addView(saveApiBtn)
        container.addView(mixUrlInput)
        container.addView(saveMixBtn)
        container.addView(overlayPermBtn)
        container.addView(accPermBtn)
        container.addView(startToibotBtn)
        container.addView(stopToibotBtn)

        rootScroll.addView(container)
        setContentView(rootScroll)
    }

    private fun requestAllPermissionsAndStart() {
        val perms = arrayOf(
            Manifest.permission.RECORD_AUDIO,
            Manifest.permission.READ_CONTACTS,
            Manifest.permission.CALL_PHONE,
            Manifest.permission.SEND_SMS,
            Manifest.permission.CAMERA
        )
        val missing = perms.filter {
            ContextCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED
        }
        if (missing.isNotEmpty()) {
            ActivityCompat.requestPermissions(this, missing.toTypedArray(), 100)
        } else {
            startToibotService()
        }
    }

    override fun onRequestPermissionsResult(
        requestCode: Int,
        permissions: Array<out String>,
        grantResults: IntArray
    ) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        if (requestCode == 100) {
            startToibotService()
        }
    }

    private fun startToibotService() {
        val intent = Intent(this, ToibotForegroundService::class.java)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(intent)
        } else {
            startService(intent)
        }
        statusLabel.text = "T.O.I.B.O.T ishga tushdi! Yuqoridagi mini-sfera faol."
    }
}
""",
}


def setup_project():
    # 1. Write all Gradle, Manifest, XML, Kotlin & Workflow files
    for rel_path, content in FILES.items():
        os.makedirs(os.path.dirname(rel_path) or ".", exist_ok=True)
        with open(rel_path, "w", encoding="utf-8") as f:
            f.write(content.lstrip("\n"))
    print(f"[OK] {len(FILES)} ta loyiha fayli yaratildi.")

    # 2. Download sherpa-onnx AAR
    os.makedirs("app/libs", exist_ok=True)
    aar_path = "app/libs/sherpa-onnx.aar"
    if not os.path.exists(aar_path):
        aar_url = "https://github.com/k2-fsa/sherpa-onnx/releases/download/v1.10.23/sherpa-onnx-v1.10.23-android.aar"
        try:
            print("[INFO] sherpa-onnx.aar yuklanmoqda...")
            urllib.request.urlretrieve(aar_url, aar_path)
            print("[OK] sherpa-onnx.aar yuklandi.")
        except Exception as e:
            print(f"[WARN] sherpa-onnx yuklanmadi: {e}")

    # 3. Download & unpack Uzbek Vosk STT model into app/src/main/assets/stt_model
    stt_target = "app/src/main/assets/stt_model"
    if not os.path.exists(os.path.join(stt_target, "am")):
        os.makedirs("app/src/main/assets", exist_ok=True)
        stt_zip = "vosk-model-small-uz-0.22.zip"
        stt_url = "https://alphacephei.com/vosk/models/vosk-model-small-uz-0.22.zip"
        try:
            print("[INFO] O'zbekcha STT model yuklanmoqda...")
            urllib.request.urlretrieve(stt_url, stt_zip)
            with zipfile.ZipFile(stt_zip, "r") as zf:
                zf.extractall("app/src/main/assets")
            extracted_dir = "app/src/main/assets/vosk-model-small-uz-0.22"
            if os.path.exists(stt_target):
                shutil.rmtree(stt_target)
            if os.path.exists(extracted_dir):
                os.rename(extracted_dir, stt_target)
            if os.path.exists(stt_zip):
                os.remove(stt_zip)
            print("[OK] O'zbekcha STT model tayyor!")
        except Exception as e:
            print(f"[WARN] STT model yuklanmadi: {e}")


if __name__ == "__main__":
    setup_project()
