package com.robotfight.offline
import android.app.Activity
import android.os.Bundle
import android.webkit.WebChromeClient
import android.webkit.WebView
import android.webkit.WebViewClient
import android.view.WindowManager
class MainActivity : Activity() {
 private lateinit var gameView: WebView
 @Suppress("SetJavaScriptEnabled")
 override fun onCreate(savedInstanceState: Bundle?) {
  super.onCreate(savedInstanceState)
  window.setFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON, WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
  gameView = WebView(this).apply {
   setBackgroundColor(android.graphics.Color.rgb(8,12,21))
   settings.javaScriptEnabled = true
   settings.domStorageEnabled = true
   settings.allowFileAccess = true
   settings.allowContentAccess = false
   settings.setSupportZoom(false)
   settings.builtInZoomControls = false
   settings.displayZoomControls = false
   webChromeClient = WebChromeClient()
   webViewClient = WebViewClient()
   isVerticalScrollBarEnabled = false
   isHorizontalScrollBarEnabled = false
   loadUrl("file:///android_asset/index.html")
  }
  setContentView(gameView)
 }
 override fun onDestroy() { if (::gameView.isInitialized) gameView.destroy(); super.onDestroy() }
}