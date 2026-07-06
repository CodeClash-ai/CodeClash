package custom;

import robocode.AdvancedRobot;
import robocode.ScannedRobotEvent;
import robocode.HitByBulletEvent;
import robocode.HitWallEvent;

/**
 * Reference bot for the CodeClash classic-Robocode arena contract and the porting example.
 *
 * The main class MUST be named MyTank and live in robots/custom/MyTank.java with `package custom;`.
 * This is a simple AdvancedRobot: oscillate, spin the radar to keep a lock, and fire with power
 * scaled to distance. Kept intentionally modest so it's a fair smoke-test opponent, not a wall.
 */
public class MyTank extends AdvancedRobot {
    private int moveDirection = 1;

    public void run() {
        // Decouple gun+radar from the body so we can aim while moving.
        setAdjustGunForRobotTurn(true);
        setAdjustRadarForGunTurn(true);
        while (true) {
            setTurnRadarRight(360);
            setAhead(120 * moveDirection);
            setTurnRight(20);
            execute();
        }
    }

    public void onScannedRobot(ScannedRobotEvent e) {
        double distance = e.getDistance();
        double power = distance > 400 ? 1.0 : (distance > 200 ? 2.0 : 3.0);

        // Simple head-on aim: turn gun toward the absolute bearing of the target.
        double absoluteBearing = getHeading() + e.getBearing();
        double gunTurn = absoluteBearing - getGunHeading();
        setTurnGunRight(normalizeBearing(gunTurn));
        if (Math.abs(gunTurn) < 10) {
            setFire(power);
        }
        // Keep the radar locked on the target.
        setTurnRadarRight(normalizeBearing(absoluteBearing - getRadarHeading()) * 2);
    }

    public void onHitByBullet(HitByBulletEvent e) {
        moveDirection = -moveDirection;
        setAhead(80 * moveDirection);
    }

    public void onHitWall(HitWallEvent e) {
        moveDirection = -moveDirection;
    }

    private double normalizeBearing(double angle) {
        while (angle > 180) angle -= 360;
        while (angle < -180) angle += 360;
        return angle;
    }
}
