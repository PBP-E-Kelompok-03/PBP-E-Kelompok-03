import datetime

from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from django.test import tag
from django.urls import reverse
from django.utils import timezone
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from accounts.models import User
from food.models import Restaurant, SurpriseBox

from .models import Order


@tag("selenium")
class OrderSeleniumBase(StaticLiveServerTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        options = Options()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1280,900")
        cls.driver = webdriver.Chrome(options=options)

    @classmethod
    def tearDownClass(cls):
        cls.driver.quit()
        super().tearDownClass()

    def setUp(self):
        self.buyer = User.objects.create_user(username="buyer1", password="pass12345")
        seller = User.objects.create_user(username="seller1", password="pass12345", role=User.Role.PARTNER)
        restaurant = Restaurant.objects.create(nama="Kedai Selenium", alamat="Jl. Test", owner=seller)
        now = timezone.now()
        self.box = SurpriseBox.objects.create(
            restaurant=restaurant,
            nama_paket="Paket Selenium",
            harga_normal=40000,
            harga_diskon=24000,
            stok=5,
            pickup_start=now - datetime.timedelta(hours=1),
            pickup_end=now + datetime.timedelta(hours=2),
        )
        self.wait = WebDriverWait(self.driver, 10)
        self.login()

    def tearDown(self):
        self.driver.delete_all_cookies()

    def login(self):
        self.driver.get(self.live_server_url + reverse("accounts:login"))
        self.driver.find_element(By.NAME, "username").send_keys("buyer1")
        self.driver.find_element(By.NAME, "password").send_keys("pass12345")
        self.click(self.driver.find_element(By.CSS_SELECTOR, "form button[type=submit]"))
        self.wait.until(lambda d: "login" not in d.current_url)

    def open_checkout(self):
        self.driver.get(self.live_server_url + reverse("order:checkout", args=[self.box.id]))
        return self.wait.until(EC.element_to_be_clickable((By.ID, "confirm-order-btn")))

    def click(self, element):
        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
        try:
            element.click()
        except Exception:
            self.driver.execute_script("arguments[0].click();", element)



@tag("selenium")
class OrderReservationSeleniumTest(OrderSeleniumBase):
    def test_reserve_shows_confirmation_with_pickup_code(self):
        self.click(self.open_checkout())
        self.wait.until(EC.url_contains("/confirmation/"))

        order = Order.objects.get()
        code = self.wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, ".voucher-code")))
        self.assertEqual(code.text, order.kode_pickup)
        self.assertIn("Reservasi berhasil", self.driver.find_element(By.TAG_NAME, "h1").text)

    def test_stepper_quantity_is_reserved(self):
        button = self.open_checkout()
        self.click(self.driver.find_element(By.ID, "stepper-plus"))
        self.assertEqual(self.driver.find_element(By.ID, "stepper-value").text, "2")
        self.click(button)
        self.wait.until(EC.url_contains("/confirmation/"))

        self.assertEqual(Order.objects.get().jumlah, 2)
        self.box.refresh_from_db()
        self.assertEqual(self.box.stok, 3)

    def test_cancel_from_confirmation_page(self):
        self.click(self.open_checkout())
        self.wait.until(EC.url_contains("/confirmation/"))
        self.click(self.wait.until(EC.element_to_be_clickable((By.ID, "cancel-btn"))))
        self.wait.until(EC.text_to_be_present_in_element((By.TAG_NAME, "h1"), "Pesanan dibatalkan"))

        self.assertEqual(Order.objects.get().status, Order.Status.CANCELLED)
        self.box.refresh_from_db()
        self.assertEqual(self.box.stok, 5)

@tag("selenium")
class OrderSellerSeleniumTest(OrderSeleniumBase):
    def login_as(self, username):
        self.driver.delete_all_cookies()
        self.driver.get(self.live_server_url + reverse("accounts:login"))
        self.driver.find_element(By.NAME, "username").send_keys(username)
        self.driver.find_element(By.NAME, "password").send_keys("pass12345")
        self.click(self.driver.find_element(By.CSS_SELECTOR, "form button[type=submit]"))
        self.wait.until(lambda d: "login" not in d.current_url)

    def test_seller_confirms_then_completes_with_code(self):
        order = Order.objects.create(pembeli=self.buyer, surprise_box=self.box, jumlah=1, kode_pickup="SEL001")
        self.login_as("seller1")
        self.driver.get(self.live_server_url + reverse("order:incoming"))

        self.click(self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-confirm-order]"))))
        code_input = self.wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, "[data-code-input]")))
        order.refresh_from_db()
        self.wait.until(lambda d: Order.objects.get(pk=order.pk).status == Order.Status.CONFIRMED)

        code_input.send_keys("SALAH1")
        self.click(self.driver.find_element(By.CSS_SELECTOR, "[data-complete-order]"))
        error = self.wait.until(EC.visibility_of_element_located((By.ID, "complete-error")))
        self.assertIn("Kode pickup tidak cocok", error.text)

        code_input.clear()
        code_input.send_keys("sel001")
        self.click(self.driver.find_element(By.CSS_SELECTOR, "[data-complete-order]"))
        self.wait.until(EC.invisibility_of_element_located((By.CSS_SELECTOR, "[data-complete-order]")))
        self.assertEqual(Order.objects.get(pk=order.pk).status, Order.Status.COMPLETED)

    def test_buyer_cancel_from_history_updates_without_reload(self):
        order = Order.objects.create(pembeli=self.buyer, surprise_box=self.box, jumlah=1, kode_pickup="HIS001")
        self.box.stok = 4
        self.box.save()
        self.driver.get(self.live_server_url + reverse("order:history"))

        self.click(self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "[data-cancel-order]"))))
        self.click(self.wait.until(EC.element_to_be_clickable((By.ID, "cancel-confirm"))))
        self.wait.until(EC.text_to_be_present_in_element((By.CSS_SELECTOR, "[data-count=cancelled]"), "1"))

        self.wait.until(lambda d: Order.objects.get(pk=order.pk).status == Order.Status.CANCELLED)
        self.box.refresh_from_db()
        self.assertEqual(self.box.stok, 5)
