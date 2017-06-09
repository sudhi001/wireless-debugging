//
//  AppDelegate.swift
//  Wireless Debug iOS Test App
//

import UIKit

@UIApplicationMain
class AppDelegate: UIResponder, UIApplicationDelegate {

    var window: UIWindow?
    let hostname = NSLocalizedString("hostname", comment: "")


    func application(_ application: UIApplication, didFinishLaunchingWithOptions launchOptions: [UIApplicationLaunchOptionsKey: Any]?) -> Bool {
        // Start the Wireless Debugger
        WirelessDebugger.start(hostname: self.hostname, apiKey: "test")
        return true
    }
}

